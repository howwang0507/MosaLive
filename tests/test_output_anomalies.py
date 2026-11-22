"""Offline tests for broken-output detection; no service or model imports."""
import json,os,sys,tempfile,unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'windows'))
import quality_checks as q
import scan_output_anomalies as scan

# Real finals from the 2026-11-07/08 FLEURS replays (A-default, E-large-turbo).
BROKEN=[
 ("If you want to be close to the action, you're going to have to get in early",'如果你想要靠近現場，你必須 EARLY � � 抵達 以 獲得 一個 靠近 的 露營地點。',
  {'replacement_character','cjk_spacing','uppercased_source_word'}),
 ('Feral children may have experienced severe child abuse','放蕩兒童可能曾在遭受嚴重!!");',{'code_residue'}),
 ('Lamb MP is expected to take the business ministry job.','Lamb � � � 博士 將 會 接 任 商 務 部 部 長 一 職。',{'replacement_character','cjk_spacing'}),
 ('Aerosmith have cancelled their remaining concerts on their tour.','Aerosmith已取消 TOUR剩餘的演唱會。',{'uppercased_source_word'}),
 ('The term bug is used by entomologists','TERMS 蟲在昆蟲學家的正式用語中是指這一群昆蟲。',{'uppercased_source_word'}),
]
CLEAN=[
 ('NASA uses a GPU for AI.','NASA 使用 GPU 進行 AI 運算。'),
 ('Use the API key.','使用 API 金鑰。'),
 ('Hello everyone, thanks for watching.','大家好，謝謝收看。'),
 ('Aerosmith have cancelled their tour.','Aerosmith 已取消剩餘的巡迴演唱會。'),
 ('He said "fine".','他說「好」。'),
 ('Lions are the most social cats.','獅子是最社會化的貓科動物（Felidae）。'),
]

class OutputAnomalyTests(unittest.TestCase):
    def test_real_broken_outputs_are_caught(self):
        for src,zh,want in BROKEN:
            with self.subTest(zh=zh):self.assertEqual(set(q.output_anomalies(src,zh)),want)

    def test_normal_output_is_not_flagged(self):
        for src,zh in CLEAN:
            with self.subTest(zh=zh):
                self.assertEqual(q.output_anomalies(src,zh),[])
                self.assertEqual(q.caps_words(src,zh),([],[]))

    def test_name_like_case_change_is_reported_but_not_repaired(self):
        src,zh='He met Jackar today.','他今天見了JACKAR。'
        self.assertEqual(q.caps_words(src,zh),([],['JACKAR']))
        self.assertEqual(q.output_anomalies(src,zh),[])
        # A Title-case word at a sentence start may be a name; stay conservative.
        self.assertEqual(q.caps_words('Think of it as a route.','THINK 它'),([],['THINK']))

    def test_source_acronyms_and_absent_words_are_ignored(self):
        self.assertEqual(q.caps_words('The GPU is fast.','GPU 很快。'),([],[]))
        self.assertEqual(q.caps_words('It is fast.','它很快 OK。'),([],[]))

    def test_repair_trial_is_off_by_default(self):
        src,zh=BROKEN[1][:2]
        with mock.patch.dict(os.environ,{},clear=False):
            os.environ.pop('MOSA_OUTPUT_ANOMALY_REPAIR',None)
            self.assertNotIn('code_residue',q.quality_flags(src,zh,'en'))
        with mock.patch.dict(os.environ,{'MOSA_OUTPUT_ANOMALY_REPAIR':'1'}):
            self.assertIn('code_residue',q.quality_flags(src,zh,'en'))
        self.assertIn('code_residue',q.quality_flags(src,zh,'en',anomalies=True))
        self.assertNotIn('code_residue',q.quality_flags(src,zh,'en',anomalies=False))

    def test_all_caps_is_reported_but_does_not_trigger_repair(self):
        src,zh=BROKEN[3][:2]
        self.assertEqual(q.output_anomalies(src,zh),['uppercased_source_word'])
        self.assertEqual(q.quality_flags(src,zh,'en',anomalies=True),[])
        src,zh=BROKEN[0][:2]
        self.assertEqual(set(q.quality_flags(src,zh,'en',anomalies=True)),{'replacement_character','cjk_spacing'})

    def test_existing_flags_unchanged(self):
        flags=q.quality_flags('I will not go.','我會去。','en',anomalies=True)
        self.assertEqual(flags,['possible_missing_negation'])

    def test_scanner_counts_and_refuses_overwrite(self):
        events=[{'type':'final','seq':1,'speech_start_ms':0,'original':BROKEN[1][0],'translation':BROKEN[1][1],'quality_flags':[]},
                {'type':'final','seq':1,'speech_start_ms':0,'original':'dup','translation':'dup'},
                {'type':'final','seq':2,'speech_start_ms':10,'original':'He met Jackar.','translation':'他見了JACKAR。'},
                {'type':'final','seq':3,'speech_start_ms':20,'original':'Hi.','translation':'嗨。'}]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'r.json';p.write_text(json.dumps({'results':[{'id':'x','events':events}]}),encoding='utf-8')
            r=scan.scan(p)[0]
            self.assertEqual(r['finals'],3)
            self.assertEqual(r['counts'],{'code_residue':1,'any_anomaly':1,'anomaly_unflagged_at_runtime':1,'name_case_changed':1})
            out=Path(d)/'o.json';out.write_text('keep',encoding='utf-8')
            with self.assertRaises(SystemExit):scan.main([str(p),'--save',str(out)])
            self.assertEqual(out.read_text(encoding='utf-8'),'keep')

if __name__=='__main__':unittest.main()
