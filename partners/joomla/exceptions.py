class JoomlaError(Exception): pass
class JoomlaConnectionError(JoomlaError): pass
class JoomlaNotImplementedError(JoomlaError): pass
class ManagedMarkerMismatch(JoomlaError): pass
class JoomlaAuthenticationError(JoomlaError): pass
class JoomlaArticleError(JoomlaError): pass
class JoomlaPermissionError(JoomlaError): pass
