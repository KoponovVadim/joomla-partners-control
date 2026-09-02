from .detector import detect_version

def get_adapter(donor):
    from .base import JoomlaAdapter
    from .joomla3 import Joomla3Adapter
    from .joomla4 import Joomla4Adapter
    from .joomla5 import Joomla5Adapter
    adapters = {"3": Joomla3Adapter, "4": Joomla4Adapter, "5": Joomla5Adapter}
    return adapters.get(donor.joomla_version, JoomlaAdapter)(donor)
