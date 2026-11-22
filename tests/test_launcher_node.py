"""windows/launch.py uses MOSA_NODE (the desktop app's bundled Node) before searching PATH."""
import io,runpy,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock

LAUNCH=Path(__file__).resolve().parents[1]/'windows/launch.py'

class LauncherNodeTests(unittest.TestCase):
    def run_until_ollama(self,env):
        sock=MagicMock();sock.__enter__.return_value.connect_ex.return_value=1
        with patch('os.chdir'),patch.dict('os.environ',env,clear=False),\
             patch('urllib.request.urlopen',side_effect=OSError('down')),patch('socket.socket',return_value=sock),\
             patch('shutil.which',side_effect=lambda name:'/usr/bin/node' if name=='node' else None) as which,\
             patch('subprocess.check_output',return_value='24\n') as version,\
             patch('subprocess.Popen') as spawn,patch('builtins.print') as output:
            runpy.run_path(str(LAUNCH),run_name='__main__')
        spawn.assert_not_called()
        self.assertIn('Ollama is unavailable',output.call_args.args[0])
        return version.call_args.args[0][0]

    def test_mosa_node_wins(self):
        self.assertEqual(self.run_until_ollama({'MOSA_NODE':'C:/MosaLive/MosaLive.exe','MOSA_NO_BROWSER':'1'}),'C:/MosaLive/MosaLive.exe')

    def test_path_node_without_override(self):
        with patch.dict('os.environ',{},clear=False):
            import os;os.environ.pop('MOSA_NODE',None)
            self.assertEqual(self.run_until_ollama({'MOSA_NO_BROWSER':'1'}),'/usr/bin/node')

if __name__=='__main__':unittest.main()
