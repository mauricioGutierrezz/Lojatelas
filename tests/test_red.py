"""Varios equipos: modo servidor, red privada únicamente y asistente."""
import os
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from unittest.mock import MagicMock, patch
from urllib.request import urlopen

from app_loja import red

ROOT = Path(__file__).resolve().parents[1]


class AllowedClientTests(unittest.TestCase):
    def test_only_this_machine_and_private_networks(self):
        for address in ('127.0.0.1', '::1', '192.168.1.35', '10.0.0.8', '172.16.4.2', '169.254.10.1',
                        '::ffff:192.168.1.9', 'fe80::1%12'):
            with self.subTest(address=address):
                self.assertTrue(red.allowed_client(address))
        for address in ('8.8.8.8', '200.45.1.2', '100.70.1.2', '2800:21:1::5', '::ffff:8.8.8.8', '', None, 'equipo'):
            with self.subTest(address=address):
                self.assertFalse(red.allowed_client(address))
        # Redes extra explícitas (p. ej. una VPN futura) se declaran; nunca se asumen.
        self.assertTrue(red.allowed_client('100.70.1.2', ('100.64.0.0/10',)))
        self.assertFalse(red.allowed_client('8.8.8.8', ('100.64.0.0/10',)))

    def test_application_refuses_public_addresses_before_any_other_work(self):
        from app_loja.run import create_app
        app = create_app({'TESTING': True, 'SECRET_KEY': 'fixture-only'})
        with patch('app_loja.db.fetchone') as query:
            outside = app.test_client().get('/login', environ_base={'REMOTE_ADDR': '8.8.8.8'})
            self.assertEqual(outside.status_code, 403)
            self.assertIn('red de la tienda', outside.get_data(as_text=True))
            self.assertNotIn('csrf', outside.get_data(as_text=True))
            self.assertIsNone(outside.headers.get('Set-Cookie'))
            self.assertEqual(app.test_client().get('/static/stock.css', environ_base={'REMOTE_ADDR': '8.8.8.8'}).status_code, 403)
            query.assert_not_called()
            inside = app.test_client().get('/login', environ_base={'REMOTE_ADDR': '192.168.1.40'})
            self.assertEqual(inside.status_code, 200)
            self.assertIn('Administrador', inside.get_data(as_text=True))
        vpn = create_app({'TESTING': True, 'SECRET_KEY': 'fixture-only', 'REDES_PERMITIDAS': ('100.64.0.0/10',)})
        self.assertEqual(vpn.test_client().get('/login', environ_base={'REMOTE_ADDR': '100.70.1.2'}).status_code, 200)

    def test_saved_mode_defaults_to_local_and_survives_bad_content(self):
        with tempfile.TemporaryDirectory(prefix='loja-red-test-') as directory, \
             patch.dict(os.environ, {'LOJA_SECRET_DIR': directory}):
            self.assertFalse(red.network_mode())
            red.set_network_mode(True)
            self.assertTrue(red.network_mode())
            self.assertEqual((Path(directory)/'modo.txt').read_text(), 'red\n')
            red.set_network_mode(False)
            self.assertFalse(red.network_mode())
            (Path(directory)/'modo.txt').write_bytes(b'\xff\xfeotra cosa')
            self.assertFalse(red.network_mode())


class StartNetworkTests(unittest.TestCase):
    def start(self, argv, saved_mode=False):
        from app_loja.start_windows import main
        store = MagicMock()
        store.available.return_value = False
        with (patch.dict(os.environ), patch.dict('app_loja.config.DB_CONFIG'),
              patch('sys.argv', ['start_windows', *argv]),
              patch('app_loja.start_windows.windows_secret', store),
              patch('app_loja.start_windows.red.network_mode', return_value=saved_mode),
              patch('app_loja.start_windows.red.urls', return_value=['http://tienda-fixture:5000']),
              patch('app_loja.start_windows.urlopen', side_effect=OSError('not listening')),
              patch('app_loja.start_windows.read_secret', return_value='fixture-secret'),
              patch('app_loja.db.fetchone', return_value={'database': 'urdimbre'}),
              patch('app_loja.run.create_app', return_value=object()),
              patch('werkzeug.serving.make_server', return_value=MagicMock()) as local,
              patch('waitress.create_server', return_value=MagicMock()) as network,
              patch('app_loja.start_windows.webbrowser.open') as browser,
              patch('builtins.print') as output):
            main()
        return local, network, browser, ' '.join(str(call) for call in output.call_args_list)

    def test_default_serves_only_this_machine(self):
        local, network, browser, printed = self.start([])
        self.assertEqual(local.call_args.args[:2], ('127.0.0.1', 5000))
        local.return_value.serve_forever.assert_called_once()
        network.assert_not_called()
        browser.assert_called_once()
        self.assertNotIn('tienda-fixture', printed)

    def test_server_mode_listens_on_the_network_and_shows_the_address(self):
        for argv, saved in ((['--red'], False), ([], True)):
            with self.subTest(argv=argv, saved=saved):
                local, network, browser, printed = self.start(argv, saved)
                local.assert_not_called()
                self.assertEqual(network.call_args.kwargs['host'], '0.0.0.0')
                self.assertEqual(network.call_args.kwargs['port'], 5000)
                network.return_value.run.assert_called_once()
                self.assertIn('http://tienda-fixture:5000', printed)
                self.assertIn('permitir_red.bat', printed)

    def test_local_flag_overrides_saved_server_mode_and_autostart_skips_browser(self):
        local, network, browser, _ = self.start(['--local'], saved_mode=True)
        local.assert_called_once()
        network.assert_not_called()
        local, network, browser, _ = self.start(['--sin-navegador'], saved_mode=True)
        network.assert_called_once()
        browser.assert_not_called()

    def test_production_server_really_answers_the_login_page(self):
        from waitress import create_server
        from app_loja.run import create_app
        server = create_server(create_app({'TESTING': True, 'SECRET_KEY': 'fixture-only'}),
                               host='127.0.0.1', port=0, threads=2, ident=None)
        port = server.socket.getsockname()[1]
        thread = Thread(target=server.run, daemon=True)
        thread.start()
        try:
            with urlopen(f'http://127.0.0.1:{port}/login', timeout=5) as response:
                page = response.read().decode('utf-8')
                self.assertEqual(response.status, 200)
                self.assertIsNone(response.headers.get('Server'))
            self.assertIn('<title>Urdimbre</title>', page)
            self.assertIn('<option value="cajero"', page)
        finally:
            server.close()
            thread.join(timeout=5)


class WizardNetworkTests(unittest.TestCase):
    def run_wizard(self, answers):
        from app_loja import instalar_windows as wizard
        with (patch('builtins.input', side_effect=answers), patch('builtins.print'),
              patch.object(wizard.red, 'network_mode', return_value=False),
              patch.object(wizard.red, 'set_network_mode') as mode,
              patch.object(wizard.red, 'urls', return_value=['http://tienda-fixture:5000']),
              patch.object(wizard, 'powershell', return_value=True) as shell):
            wizard.configure_network()
        return wizard, mode, shell

    def test_single_machine_changes_nothing_else(self):
        _wizard, mode, shell = self.run_wizard(['n'])
        mode.assert_called_once_with(False)
        shell.assert_not_called()

    def test_server_writes_client_link_and_asks_before_firewall_and_autostart(self):
        wizard, mode, shell = self.run_wizard(['s', 'n', 'n'])
        mode.assert_called_once_with(True)
        self.assertEqual([call.args[0] for call in shell.call_args_list], [wizard.URL_FILE])
        self.assertEqual(shell.call_args.kwargs['LOJA_URL'], 'http://tienda-fixture:5000/')
        wizard, mode, shell = self.run_wizard(['S', 'sí', 'si'])
        scripts = [call.args[0] for call in shell.call_args_list]
        self.assertEqual(scripts, [wizard.URL_FILE, wizard.ELEVATE, wizard.SHORTCUT])
        self.assertEqual(Path(shell.call_args_list[1].kwargs['LOJA_ELEVATE_TARGET']).name, 'permitir_red.bat')
        startup = shell.call_args_list[2].kwargs
        self.assertEqual((startup['LOJA_SHORTCUT_FOLDER'], startup['LOJA_SHORTCUT_ARGUMENTS'], startup['LOJA_SHORTCUT_STYLE']),
                         ('Startup', '--sin-navegador', 7))

    def test_firewall_script_opens_only_the_private_local_subnet(self):
        script = (ROOT/'permitir_red.bat').read_text(encoding='ascii').lower()
        rules = [line for line in script.splitlines() if 'firewall add rule' in line]
        self.assertEqual(len(rules), 1)
        for expected in ('dir=in', 'action=allow', 'protocol=tcp', 'localport=5000', 'profile=private', 'remoteip=localsubnet'):
            self.assertIn(expected, rules[0])
        for forbidden in ('profile=any', 'profile=public', 'remoteip=any', '5432'):
            self.assertNotIn(forbidden, script)
        # La regla que se quita es exactamente la que se creó.
        name = rules[0].split('name=')[1].split(' dir=')[0]
        self.assertIn(f'firewall delete rule name={name}', (ROOT/'quitar_red.bat').read_text(encoding='ascii').lower())

    def test_missing_icon_does_not_touch_the_session_or_redirect_to_login(self):
        from app_loja.run import create_app
        response = create_app({'TESTING': True, 'SECRET_KEY': 'fixture-only'}).test_client().get('/favicon.ico')
        self.assertEqual(response.status_code, 204)
        self.assertIsNone(response.headers.get('Set-Cookie'))


if __name__ == '__main__':
    unittest.main()
