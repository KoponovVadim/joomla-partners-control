from .detector import detect_version


def get_adapter(donor):
    from .base import JoomlaAdapter
    from .joomla3 import Joomla3Adapter
    from .joomla3_connector import Joomla3ConnectorAdapter
    from .joomla4 import Joomla4Adapter
    from .joomla5 import Joomla5Adapter

    if (
        donor.joomla_version == "3"
        and donor.auth_mode == "connector_token"
    ):
        return Joomla3ConnectorAdapter(donor)

    adapters = {
        "3": Joomla3Adapter,
        "4": Joomla4Adapter,
        "5": Joomla5Adapter,
    }
    return adapters.get(donor.joomla_version, JoomlaAdapter)(donor)
