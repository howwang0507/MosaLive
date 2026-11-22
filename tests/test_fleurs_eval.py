import io,json,struct,sys,tarfile,tempfile,unittest,wave
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'windows'))
import numpy as np
import build_fleurs_eval as builder
import score_eval as scorer

def wav_bytes(rate=16000,channels=1,tone_s=1.0,edge_s=.3):
    t=np.arange(int(rate*tone_s))/rate;tone=.2*np.sin(2*np.pi*220*t)
    edge=np.zeros(int(rate*edge_s));mono=np.concatenate([edge,tone,edge])
    data=np.repeat(mono[:,None],channels,axis=1).reshape(-1)
    out=io.BytesIO()
    with wave.open(out,'wb') as f:f.setnchannels(channels);f.setsampwidth(2);f.setframerate(rate);f.writeframes((data*32767).astype('<i2').tobytes())
    return out.getvalue()

class FleursBuildTests(unittest.TestCase):
    def test_trim_preserves_quiet_speech_around_louder_click(self):
        t=np.arange(16000)/16000
        speech=(.002*np.sin(2*np.pi*220*t)).astype(np.float32)
        speech[7900:8100]=.03
        audio=np.concatenate([np.zeros(4800,np.float32),speech,np.zeros(4800,np.float32)])
        trimmed=builder.trim(audio)
        self.assertGreaterEqual(len(trimmed),len(speech))
        self.assertLess(len(trimmed),len(audio))

    def test_decodes_fleurs_float_wav_and_resamples_stereo(self):
        # Real FLEURS archives use IEEE float WAV (format 3), unsupported by wave.open on Python 3.11.
        samples=np.full((800,2),.25,dtype='<f4').tobytes()
        fmt=struct.pack('<HHIIHH',3,2,8000,64000,8,32)
        chunks=b'fmt '+struct.pack('<I',len(fmt))+fmt+b'data'+struct.pack('<I',len(samples))+samples
        audio=builder.decode(b'RIFF'+struct.pack('<I',len(chunks)+4)+b'WAVE'+chunks)
        self.assertEqual(audio.dtype,np.float32)
        self.assertEqual(audio.ndim,1)
        self.assertEqual(len(audio),1600)
        np.testing.assert_allclose(audio,.25,atol=1/32768)

    def setUp(self):
        self.dir=Path(tempfile.mkdtemp())
        # Rows are deliberately out of order; id 5 has no Mandarin reference, id 4 no English audio.
        en=[('3','c.wav','Wait 3 minutes.'),('1','a.wav','I did not go.'),('2','b.wav','Hello there.'),('5','e.wav','Unpaired sentence.')]
        zh=[('2','z2.wav','你好。'),('4','z4.wav','没有英文。'),('1','z1.wav','我没有去。'),('3','z3.wav','等3分钟。')]
        row=lambda i,f,t:'\t'.join([i,f,t,t.lower(),'_','26000','FEMALE'])+'\n'
        (self.dir/'en.tsv').write_text(''.join(row(*r) for r in en),encoding='utf-8')
        (self.dir/'zh.tsv').write_text(''.join(row(*r) for r in zh),encoding='utf-8')
        with tarfile.open(self.dir/'audio.tar.gz','w:gz') as tar:
            for name,data in (('a.wav',wav_bytes()),('b.wav',wav_bytes(rate=8000,channels=2)),('c.wav',wav_bytes()),('e.wav',wav_bytes())):
                info=tarfile.TarInfo('test/'+name);info.size=len(data);tar.addfile(info,io.BytesIO(data))

    def test_pairs_by_sentence_id_and_writes_aligned_stream(self):
        out=Path(tempfile.mkdtemp())
        wav,ref,manifest,info=builder.build(self.dir/'en.tsv',self.dir/'zh.tsv',self.dir/'audio.tar.gz',out,'t',1,7,'abc123',lambda s:s.replace('没','沒').replace('钟','鐘'))
        self.assertEqual(info['sentences'],3);self.assertEqual(info['revision'],'abc123')
        pairs={s['fleurs_id']:(s['source'],s['reference_zh_hans'],s['reference_zh_tw']) for s in info['segments']}
        self.assertEqual(pairs[1],('I did not go.','我没有去。','我沒有去。'))
        self.assertEqual(pairs[3][1],'等3分钟。');self.assertNotIn(5,pairs)
        self.assertEqual(info['tag_coverage'],{'number':1,'negation':1,'condition':0})
        with wave.open(str(wav)) as f:
            self.assertEqual((f.getnchannels(),f.getframerate(),f.getsampwidth()),(1,16000,2))
            audio=np.frombuffer(f.readframes(f.getnframes()),'<i2').astype(np.float32)/32768
        self.assertAlmostEqual(len(audio)/16,info['duration_ms'],delta=1)
        for a,b in zip(info['segments'],info['segments'][1:]):
            self.assertGreaterEqual(b['start_ms']-a['end_ms'],150)                     # seeded gap
            gap=audio[int(a['end_ms']*16)+10:int(b['start_ms']*16)-10];self.assertLess(np.abs(gap).max(),1e-3)
        for s in info['segments']:
            clip=audio[int(s['start_ms']*16):int(s['end_ms']*16)]
            self.assertLess(len(clip)/16000,1.25)                                       # 0.3 s edges trimmed to ~0.1 s
            self.assertGreater(np.abs(clip).max(),.15)
        sample=json.loads(manifest.read_text(encoding='utf-8'))['samples'][0]
        self.assertTrue(Path(sample['path']).exists());self.assertTrue(Path(sample['reference']).exists())
        again=builder.build(self.dir/'en.tsv',self.dir/'zh.tsv',self.dir/'audio.tar.gz',out,'t2',1,7)[3]
        self.assertEqual([s['start_ms'] for s in again['segments']],[s['start_ms'] for s in info['segments']])  # deterministic

def wav_from(signal):
    out=io.BytesIO()
    with wave.open(out,'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes((np.clip(signal,-1,1)*32767).astype('<i2').tobytes())
    return out.getvalue()

def tone(amplitude,seconds=1.0):
    return (amplitude*np.sin(2*np.pi*220*np.arange(int(16000*seconds))/16000)).astype(np.float32)

class LevelVariantTests(unittest.TestCase):
    """Level-normalized variant: same sentences, order, gaps and timing; only per-clip gain differs."""
    def setUp(self):
        self.dir=Path(tempfile.mkdtemp())
        click=tone(.02);click[8000:8040]=.9
        clips={'loud.wav':tone(.2),'quiet.wav':tone(.001),'click.wav':click,'faint.wav':tone(1e-4),'silent.wav':np.zeros(16000,np.float32)}
        en=[(str(i),name,f'Sentence {i}.') for i,name in enumerate(clips,1)]
        row=lambda i,f,t:'\t'.join([i,f,t,t.lower(),'_','16000','FEMALE'])+'\n'
        (self.dir/'en.tsv').write_text(''.join(row(*r) for r in en),encoding='utf-8')
        (self.dir/'zh.tsv').write_text(''.join(row(i,'z'+f,f'第{i}句。') for i,f,_ in en),encoding='utf-8')
        with tarfile.open(self.dir/'audio.tar.gz','w:gz') as tar:
            for name,signal in clips.items():
                data=wav_from(signal);info=tarfile.TarInfo('test/'+name);info.size=len(data);tar.addfile(info,io.BytesIO(data))

    def build(self,out,name,loudness=None,match=None):
        return builder.build(self.dir/'en.tsv',self.dir/'zh.tsv',self.dir/'audio.tar.gz',out,name,1,3,'r',None,None,loudness,match)

    def test_active_speech_level_ignores_pauses_and_differs_from_peak(self):
        clip=np.concatenate([tone(.1),np.zeros(48000,np.float32)])
        level=builder.levels(clip)
        self.assertAlmostEqual(level['active_rms_dbfs'],20*np.log10(.1/np.sqrt(2)),delta=.2)   # whole-clip RMS would be 6 dB lower
        self.assertAlmostEqual(level['peak_dbfs'],-20,delta=.1)
        self.assertIsNone(builder.levels(np.zeros(16000,np.float32))['active_rms_dbfs'])

    def test_variant_keeps_timeline_and_records_bounded_gain(self):
        raw_out,norm_out=Path(tempfile.mkdtemp()),Path(tempfile.mkdtemp())
        raw=self.build(raw_out,'raw')[3]
        norm=self.build(norm_out,'norm',-20,raw)[3]
        self.assertEqual(norm['timeline_sha256'],raw['timeline_sha256'])
        self.assertEqual([(s['fleurs_id'],s['start_ms'],s['end_ms']) for s in norm['segments']],[(s['fleurs_id'],s['start_ms'],s['end_ms']) for s in raw['segments']])
        self.assertEqual(raw['loudness']['variant'],'original level (no gain)')
        self.assertTrue(all(s['level']['gain_db']==0 for s in raw['segments']))
        level={s['file']:s['level'] for s in norm['segments']}
        self.assertAlmostEqual(level['quiet.wav']['output_active_rms_dbfs'],-20,delta=.3)
        self.assertGreater(level['quiet.wav']['gain_db'],40)
        self.assertTrue(level['click.wav']['peak_limited']);self.assertAlmostEqual(level['click.wav']['output_peak_dbfs'],-1,delta=.1)
        self.assertLess(level['click.wav']['output_active_rms_dbfs'],-20)                  # gain reduced, not clipped
        self.assertTrue(level['faint.wav']['gain_capped']);self.assertEqual(level['faint.wav']['gain_db'],builder.MAX_GAIN_DB)
        self.assertTrue(level['silent.wav']['no_active_speech']);self.assertEqual(level['silent.wav']['gain_db'],0)
        self.assertEqual((norm['loudness']['peak_limited'],norm['loudness']['gain_capped'],norm['loudness']['no_active_speech']),(1,1,1))

    def test_mismatched_timeline_aborts_before_writing(self):
        raw=self.build(Path(tempfile.mkdtemp()),'raw')[3]
        raw=json.loads(json.dumps(raw));raw['segments'][0]['start_ms']+=1;raw.pop('timeline_sha256')
        out=Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError):self.build(out,'norm',-20,raw)
        self.assertEqual(list(out.iterdir()),[])

    def test_refuses_to_overwrite_existing_outputs(self):
        out=Path(tempfile.mkdtemp());self.build(out,'raw')
        with self.assertRaises(FileExistsError):self.build(out,'raw')

class FleursDownloadTests(unittest.TestCase):
    def test_no_credentials_and_one_pinned_commit_for_every_file(self):
        sha='a'*40;seen=[]
        class Response(io.BytesIO):
            headers={}
            def __enter__(self):return self
            def __exit__(self,*a):pass
        def urlopen(request,timeout=0):
            seen.append(request);return Response(json.dumps({'sha':sha}).encode() if '/api/' in request.full_url else b'data')
        out=Path(tempfile.mkdtemp())
        with patch.dict('os.environ',{'HF_TOKEN':'fake-token-never-sent'}),patch.object(builder.urllib.request,'urlopen',urlopen):
            revision=builder.resolve_revision('main')
            for key,(lang,name) in builder.FILES.items():
                builder.fetch(builder.REPO.format(revision=revision,lang=lang,path=name),out/lang/name)
        self.assertEqual(revision,sha);self.assertEqual(len(seen),4)
        self.assertTrue(all(not r.has_header('Authorization') for r in seen))
        self.assertTrue(all(f'/resolve/{sha}/' in r.full_url for r in seen[1:]))
        self.assertEqual(builder.sha256(out/'en_us'/'test.tsv'),'3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7')

    def test_commit_ids_are_used_as_is(self):
        with patch.object(builder.urllib.request,'urlopen',side_effect=AssertionError('no lookup')):
            self.assertEqual(builder.resolve_revision('b'*40),'b'*40)

def reference():
    return {'segments':[
        dict(index=0,fleurs_id=1,start_ms=0,end_ms=2000,source='I did not go.',reference_zh_hans='我没有去。',reference_zh_tw='我沒有去。',tags=['negation']),
        dict(index=1,fleurs_id=2,start_ms=2500,end_ms=4500,source='Wait 3 minutes.',reference_zh_hans='等3分钟。',reference_zh_tw='等3分鐘。',tags=['number']),
        dict(index=2,fleurs_id=3,start_ms=5000,end_ms=6000,source='Hello there.',reference_zh_hans='你好。',reference_zh_tw='你好。',tags=[])]}

def final(seq,start,end,original,translation,delay=1500,reason='silence'):
    return dict(type='final',seq=seq,speech_start_ms=start,speech_end_ms=end,original=original,translation=translation,
                capture_to_caption_ms=end-start+delay,after_speech_ms=delay,endpoint_reason=reason)

def run(events,ref=None):return scorer.score({'id':'x','events':events,'metrics':{}},ref or reference())

class ScoreTests(unittest.TestCase):
    def test_perfect_run(self):
        report=run([final(0,0,2000,'I did not go.','我沒有去。'),final(1,2500,4500,'Wait 3 minutes.','等3分鐘。'),final(2,5000,6000,'Hello there.','你好。')])
        self.assertEqual((report['asr']['wer_raw'],report['asr']['wer_numbers_normalized']),(0,0))
        self.assertEqual(report['translation']['chrf_document'],100.0)
        self.assertEqual(report['checks']['needs_review'],[]);self.assertEqual(report['checks']['covered'],3)
        self.assertEqual(report['availability']['sentence_end_to_final_ms_p50'],1500)

    def test_split_captions_are_not_penalised_and_errors_are_flagged(self):
        # Sentence 0 arrives as two captions (segmentation-free scoring); negation and the number are lost.
        report=run([final(0,0,900,'I did','我有'),final(1,900,2000,'go.','去。'),final(2,2500,4500,'Wait three minutes.','等幾分鐘。')])
        checks=report['checks']
        self.assertEqual((checks['negation_without_marker'],checks['translation_number_misses'],checks['asr_number_misses']),(1,1,0))
        self.assertEqual((checks['covered'],checks['missing']),(2,1))
        self.assertAlmostEqual(report['asr']['wer_numbers_normalized'],3/9,places=4)   # three == 3
        self.assertAlmostEqual(report['asr']['wer_raw'],4/9,places=4)                  # raw keeps three != 3
        self.assertEqual(sorted(checks['needs_review']),[0,1,2])

    def test_sign_and_decimal_are_not_normalized_away(self):
        for ref,hyp in (('It fell to -3 degrees.','It fell to 3 degrees.'),('It costs 3.5 dollars.','It costs 3 5 dollars.')):
            self.assertGreater(scorer.wer(ref,hyp,True),0,(ref,hyp))
        self.assertEqual(scorer.wer('It costs 1,200 dollars.','It costs twelve hundred dollars.',True),0)
        sign={'segments':[dict(index=0,fleurs_id=1,start_ms=0,end_ms=2000,source='It fell to -3 degrees.',reference_zh_hans='降到零下3度。',reference_zh_tw='降到零下3度。',tags=['number'])]}
        checks=run([final(0,0,2000,'It fell to 3 degrees.','降到3度。')],sign)['checks']
        self.assertEqual((checks['asr_sign_changes'],checks['negative_values_to_review']),(1,1))
        checks=run([final(0,0,2000,'It fell to -3 degrees.','降到零下3度。')],sign)['checks']
        self.assertEqual((checks['asr_sign_changes'],checks['negative_values_to_review']),(0,0))

    def test_no_overlap_is_never_counted_as_covered(self):
        # Caption ends at 850 ms, reference starts at 1000 ms: within tolerance, but no overlap.
        ref={'segments':[dict(index=0,fleurs_id=1,start_ms=1000,end_ms=2000,source='Wait 3 minutes.',reference_zh_hans='等3分钟。',reference_zh_tw='等3分鐘。',tags=['number'])]}
        report=run([final(0,0,850,'Wait 3 minutes.','等3分鐘。')],ref)
        self.assertEqual((report['checks']['covered'],report['checks']['boundary_only']),(0,1))
        self.assertIsNone(report['sentences'][0]['translation_missing_numbers'])   # checks not run, not "passed"
        self.assertEqual(report['checks']['needs_review'],[0])
        self.assertEqual(run([final(0,0,1001,'Wait 3 minutes.','等3分鐘。')],ref)['checks']['covered'],1)

    def test_clip_end_metric_keeps_trailing_background_and_negative_values(self):
        # Speech ends at 1200 ms but the reference clip runs to 2000 ms (room noise). The legacy
        # "within 300 ms of clip end" rule finds nothing; the new metric keeps -300 ms as is.
        report=run([final(0,0,1200,'I did not go.','我沒有去。',delay=500)],{'segments':reference()['segments'][:1]})
        availability=report['availability']
        self.assertIsNone(availability['sentence_end_to_final_ms_p50'])
        self.assertEqual(availability['clip_end_to_last_final_ms_p50'],-300.0)
        self.assertEqual((availability['clip_end_to_last_final_measured'],availability['clip_end_to_last_final_negative']),(1,1))
        self.assertEqual(report['run']['scorer_version'],scorer.SCORER_VERSION)

    def test_clip_end_metric_cross_sentence_final_and_missing_sentence(self):
        # One final spans sentences 0 and 1; sentence 2 is never captioned.
        report=run([final(0,0,4500,'I did not go. Wait 3 minutes.','我沒有去。等3分鐘。',delay=700)])
        per={p['index']:p['clip_end_to_last_final_ms'] for p in report['sentences']}
        self.assertEqual(per,{0:3200.0,1:700.0,2:None})
        self.assertEqual(report['availability']['clip_end_to_last_final_measured'],2)

    def test_asr_errors_grouped_by_original_level(self):
        ref=reference()
        for s,db in zip(ref['segments'],(-65,-40,-22)):s['level']={'original_active_rms_dbfs':db,'gain_db':0}
        rows=run([final(1,2500,4500,'Wait 3 minutes.','等3分鐘。'),final(2,5000,6000,'Hello there.','你好。')],ref)['asr']['by_original_level']
        self.assertEqual([(r['group'],r['wer']) for r in rows],[('quietest third',1.0),('middle third',0.0),('loudest third',0.0)])
        self.assertIsNone(run([])['asr']['by_original_level'])          # old references without levels

    def test_preview_shadow_counts_rewrites(self):
        preview=dict(type='partial',phase='stable',seq=0,speech_start_ms=0,speech_end_ms=1000,translation='我會去',capture_to_caption_ms=1200)
        stats=run([preview,final(0,0,2000,'I did not go.','我沒有去。')])['preview_shadow']['stable_phase']
        self.assertEqual((stats['captions'],stats['available_earlier_ms_p50'],stats['final_not_prefixed_by_first']),(1,2300,1.0))

    def test_nearest_rank_percentile(self):
        values=list(range(1,21))
        self.assertEqual(scorer.pct(values,.95),19);self.assertEqual(scorer.pct(values,.5),10)

    def test_chrf_basics(self):
        self.assertEqual(scorer.chrf('你好','你好'),100.0);self.assertEqual(scorer.chrf('','你好'),0.)
        self.assertLess(scorer.chrf('我有去','我沒有去'),100)

class LatencyComparabilityTests(unittest.TestCase):
    def report(self,tokens_per_second=54.5,asr_ms=125,finals=40,calls=200,model='qwen2.5:7b',device='cuda',tuning=None):
        events=[dict(final(i,i*1000,i*1000+800,'Hello there.','你好。'),asr_ms=asr_ms) for i in range(finals)]
        health={'models':{'translation':model,'asr':'small','device':device,'tuning':tuning or {'pause_ms':896,'asr_echo_retry':False}}}
        after={'models':{'ollama':{'calls':calls,'tokens_per_second_p50':tokens_per_second}}}
        return scorer.score({'id':'x','events':events,'metrics':{},'health':health,'health_after':after,'asrMode':'stream-en'},reference())

    def check(self,a,b):return scorer.latency_comparability(a,b)

    def test_same_speed_and_settings_are_comparable(self):
        self.assertEqual(self.check(self.report(),self.report(tokens_per_second=52,asr_ms=130))['status'],'comparable')

    def test_throughput_drop_is_flagged_without_touching_quality(self):
        # 2026-10-24 rerun: Ollama 54.5 -> 37.4 tokens/s and ASR 125 -> 172 ms in the same code path.
        base,slow=self.report(),self.report(tokens_per_second=37.4,asr_ms=172)
        check=self.check(base,slow)
        self.assertEqual(check['status'],'machine speed differs');self.assertEqual(len(check['reasons']),2)
        self.assertEqual((slow['asr'],slow['translation'],slow['checks']),(base['asr'],base['translation'],base['checks']))

    def test_single_setting_ab_uses_only_proxies_it_cannot_change(self):
        # 2026-10-25 echo guard A/B: retries add ASR time, so only Ollama tokens/s judges machine speed.
        on=self.report(tokens_per_second=47.2,asr_ms=171,tuning={'pause_ms':896,'asr_echo_retry':True})
        check=self.check(self.report(tokens_per_second=46.9,asr_ms=125),on)
        self.assertEqual(check['status'],'A/B on tuning.asr_echo_retry');self.assertEqual(check['speed_proxies'],['Ollama tokens/s p50'])
        slow=self.report(tokens_per_second=40,tuning={'pause_ms':896,'asr_echo_retry':True})
        self.assertEqual(self.check(self.report(tokens_per_second=46.9),slow)['status'],'machine speed differs')
        model=self.check(self.report(),self.report(model='gemma3:4b',tokens_per_second=80))
        self.assertEqual((model['status'],model['speed_proxies']),('A/B on translation',['own ASR p50']))

    def test_confounded_and_insufficient_cases(self):
        both=self.check(self.report(),self.report(tuning={'pause_ms':640,'asr_echo_retry':True}))
        self.assertEqual(both['status'],'A/B on tuning.asr_echo_retry, tuning.pause_ms (confounded)')
        self.assertEqual(self.check(self.report(),self.report(model='gemma3:4b',device='cpu'))['status'],'insufficient data')
        self.assertEqual(self.check(self.report(),self.report(finals=10))['status'],'insufficient data')
        self.assertEqual(self.check(self.report(),self.report(calls=20))['status'],'insufficient data')

if __name__=='__main__':unittest.main()
