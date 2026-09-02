class JoomlaError(Exception): pass
class JoomlaConnectionError(JoomlaError): pass
class JoomlaNotImplementedError(JoomlaError): pass
class ManagedMarkerMismatch(JoomlaError): pass

