"""Point a frozen bundle's OpenSSL at the bundled certifi CA store.

PyInstaller ships its own OpenSSL whose compiled-in default certificate paths
(OPENSSLDIR) point inside the *build* machine and do not exist on an end user's
machine. The stdlib ``ssl`` default context therefore loads zero trusted CAs, so
every HTTPS model-weight download fails with
``CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`` even though
the network is fine.

certifi *is* bundled (``_internal/certifi/cacert.pem``); exporting
``SSL_CERT_FILE`` / ``SSL_CERT_DIR`` makes OpenSSL — and thus urllib / requests /
torch.hub — pick it up. This mirrors what the python.org installer's
"Install Certificates.command" does.

No-op unless frozen (the dev/test interpreter has a working system trust store)
and never overrides a user-provided ``SSL_CERT_FILE``.
"""

from __future__ import annotations

import os
import sys


def configure_ssl_cert_file() -> str | None:
    """Export ``SSL_CERT_FILE``/``SSL_CERT_DIR`` from bundled certifi when frozen.

    Returns the cert path that was set (or the pre-existing one), or ``None`` if
    nothing was configured. Safe to call more than once.
    """
    if not getattr(sys, "frozen", False):
        return os.environ.get("SSL_CERT_FILE")
    existing = os.environ.get("SSL_CERT_FILE")
    if existing:
        return existing
    try:
        import certifi
    except ImportError:
        return None
    cafile = certifi.where()
    if not os.path.isfile(cafile):
        return None
    os.environ["SSL_CERT_FILE"] = cafile
    os.environ.setdefault("SSL_CERT_DIR", os.path.dirname(cafile))
    return cafile
