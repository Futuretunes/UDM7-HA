"""Root conftest: stub out homeassistant and voluptuous before test collection.

This allows pure unit tests of the API layer to run without Home Assistant
installed.  The stubs are intentionally minimal -- just enough to let the
``custom_components.unifi_network_ha`` package be importable.
"""
import sys
import types


def _make_stub(name: str) -> types.ModuleType:
    """Create a stub module that returns a new stub for any attribute access."""
    mod = types.ModuleType(name)

    class _Anything:
        """A callable/subscriptable stand-in for any HA object."""
        def __init__(self, *a, **kw): pass
        def __call__(self, *a, **kw): return self
        def __getattr__(self, _name): return _Anything()
        def __getitem__(self, _key): return _Anything()
        def __class_getitem__(cls, _key): return cls
        def __mro_entries__(self, bases): return (_Anything,)
        def __bool__(self): return False
        def __iter__(self): return iter([])

    mod.__dict__["__getattr__"] = lambda name: _Anything()
    mod.__dict__["__path__"] = []
    return mod


# Modules that need stubbing (homeassistant + its common sub-packages,
# voluptuous which services.py imports at module scope).
_STUBS = [
    "homeassistant",
    "homeassistant.config_entries",
    "homeassistant.core",
    "homeassistant.const",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.config_validation",
    "homeassistant.helpers.entity",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.helpers.device_registry",
    "homeassistant.helpers.event",
    "homeassistant.helpers.typing",
    "homeassistant.components",
    "homeassistant.components.sensor",
    "homeassistant.components.binary_sensor",
    "homeassistant.components.switch",
    "homeassistant.components.button",
    "homeassistant.components.update",
    "homeassistant.components.light",
    "homeassistant.components.image",
    "homeassistant.components.device_tracker",
    "homeassistant.components.event",
    "homeassistant.exceptions",
    "homeassistant.util",
    "homeassistant.util.dt",
    "voluptuous",
    "voluptuous.error",
]


def pytest_configure(config):
    """Inject stubs before any test modules are collected."""
    for name in _STUBS:
        if name not in sys.modules:
            sys.modules[name] = _make_stub(name)
