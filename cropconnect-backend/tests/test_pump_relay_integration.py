# Integration-style coverage for relay parsing and command text formatting.
import unittest

from pump_control import relay_command_text
from routers.pumps import parse_relay_states


class PumpRelayIntegrationTests(unittest.TestCase):
    def test_parse_relay_states_accepts_common_key_formats(self):
        states = parse_relay_states({"relay1": "on", "r2": "1", "3": "true", "RELAY4": "yes", "relay5": "off"})

        self.assertTrue(states[1])
        self.assertTrue(states[2])
        self.assertTrue(states[3])
        self.assertTrue(states[4])
        self.assertFalse(states[5])

    def test_relay_command_text_plaintext_output(self):
        command = relay_command_text({1: True, 2: False, 8: True})
        self.assertEqual(command, "1on 2off 3off 4off 5off 6off 7off 8on")


if __name__ == "__main__":
    unittest.main()
