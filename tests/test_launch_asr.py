"""resolve_asr() from windows/launch.py, extracted by AST so the launcher itself does not run."""
import ast,os,tempfile,unittest
from pathlib import Path
SRC=Path(__file__).resolve().parents[1]/'windows'/'launch.py'

def load():
    tree=ast.parse(SRC.read_text(encoding='utf-8'))
    keep=[n for n in tree.body if (isinstance(n,ast.Assign) and any(getattr(t,'id','')=='LOCAL_ASR_REPOS' for t in n.targets))
          or (isinstance(n,ast.FunctionDef) and n.name=='resolve_asr')]
    ns={'Path':Path,'root':Path('.')}
    exec(compile(ast.Module(body=keep,type_ignores=[]),str(SRC),'exec'),ns)
    return ns['resolve_asr']

class ResolveAsrTests(unittest.TestCase):
    def setUp(self):self.resolve=load()
    def snapshot(self,base):
        d=Path(base)/'models--mobiuslabsgmbh--faster-whisper-large-v3-turbo'/'snapshots'/'abc';d.mkdir(parents=True)
        (d/'model.bin').write_bytes(b'x');return d

    def test_project_cache_first(self):
        with tempfile.TemporaryDirectory() as r,tempfile.TemporaryDirectory() as h:
            d=self.snapshot(Path(r)/'.models/windows');self.snapshot(Path(h)/'.cache/huggingface/hub')
            env=self.resolve({'MOSA_ASR_MODEL':'large-v3-turbo'},root=Path(r),home=Path(h))
            self.assertEqual(env['MOSA_ASR_MODEL'],str(d));self.assertEqual(env['MOSA_ASR_LABEL'],'large-v3-turbo')

    def test_user_hf_cache_and_hf_home(self):
        with tempfile.TemporaryDirectory() as r,tempfile.TemporaryDirectory() as h:
            d=self.snapshot(Path(h)/'.cache/huggingface/hub')
            self.assertEqual(self.resolve({'MOSA_ASR_MODEL':'large-v3-turbo'},root=Path(r),home=Path(h))['MOSA_ASR_MODEL'],str(d))
            d2=self.snapshot(Path(h)/'custom/hub')
            env=self.resolve({'MOSA_ASR_MODEL':'large-v3-turbo','HF_HOME':str(Path(h)/'custom')},root=Path(r),home=Path(h))
            self.assertEqual(env['MOSA_ASR_MODEL'],str(d2))

    def test_missing_falls_back_to_small_without_download(self):
        with tempfile.TemporaryDirectory() as r,tempfile.TemporaryDirectory() as h:
            env=self.resolve({'MOSA_ASR_MODEL':'large-v3-turbo'},root=Path(r),home=Path(h))
            self.assertEqual(env['MOSA_ASR_MODEL'],'small');self.assertIn('fallback',env['MOSA_ASR_LABEL'])
            # a snapshot without model.bin is incomplete and must not be used
            d=Path(h)/'.cache/huggingface/hub/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/snapshots/x';d.mkdir(parents=True)
            self.assertEqual(self.resolve({'MOSA_ASR_MODEL':'large-v3-turbo'},root=Path(r),home=Path(h))['MOSA_ASR_MODEL'],'small')

    def test_other_values_untouched(self):
        for value in ('small','C:/models/custom',None):
            env={} if value is None else {'MOSA_ASR_MODEL':value}
            self.assertEqual(self.resolve(dict(env)),env)

if __name__=='__main__':unittest.main()
