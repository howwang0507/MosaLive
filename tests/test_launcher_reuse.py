import io,json,runpy,unittest
from pathlib import Path
from unittest.mock import patch

LAUNCH=Path(__file__).resolve().parents[1]/'windows/launch.py'

class LauncherReuseTests(unittest.TestCase):
    def test_existing_service_is_reused_without_spawning_processes(self):
        for ready in (True,False):
            with self.subTest(ready=ready),patch('os.chdir'),patch.dict('os.environ',{'MOSA_NO_BROWSER':'1'}),\
                 patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps({'app':'mosasub-live-local','ready':ready}).encode())),\
                 patch('subprocess.Popen') as spawn,patch('webbrowser.open') as browser,patch('builtins.print') as output:
                with self.assertRaises(SystemExit) as stopped:runpy.run_path(str(LAUNCH),run_name='__main__')
                self.assertEqual(stopped.exception.code,0)
                spawn.assert_not_called();browser.assert_not_called()
                self.assertIn('already running' if ready else 'not ready',output.call_args.args[0])

if __name__=='__main__':unittest.main()
