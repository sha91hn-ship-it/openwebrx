from .receiverid import ReceiverIdController
from owrx.version import openwebrx_version
from owrx.sdr import SdrService
from owrx.config import Config
from owrx.controllers.admin import Authentication
from owrx.jsons import Encoder
import json

import logging

logger = logging.getLogger(__name__)


class StatusController(ReceiverIdController):
    def getProfileStats(self, profile):
        return {
            "name": profile["name"],
            "center_freq": profile["center_freq"],
            "sample_rate": profile["samp_rate"],
        }

    def getReceiverStats(self, receiver, authenticated):
        stats = {
            "name": receiver.getName(),
            # TODO would be better to have types from the config here
            "type": type(receiver).__name__,
            "profiles": [
                self.getProfileStats(p) for p in receiver.getProfiles().values()
                if authenticated or "login_required" not in p or not p["login_required"]
            ],
        }
        return stats

    def indexAction(self):
        user = Authentication().getUser(self.request)
        authenticated = user is not None and user.is_enabled() and not user.must_change_password
        pm = Config.get()
        status = {
            "receiver": {
                "name": pm["receiver_name"],
                "admin": pm["receiver_admin"],
                "gps": pm["receiver_gps"],
                "asl": pm["receiver_asl"],
                "location": pm["receiver_location"],
            },
            "max_clients": pm["max_clients"],
            "version": openwebrx_version,
            "sdrs": [self.getReceiverStats(r, authenticated) for r in SdrService.getActiveSources().values()],
        }
        self.send_response(
            json.dumps(status, cls=Encoder),
            content_type="application/json",
            headers={"Cache-Control": "private, no-store"},
        )
