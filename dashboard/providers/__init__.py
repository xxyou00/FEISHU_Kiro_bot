from dashboard.providers.aws import AWSProvider

_REGISTRY = {
    "aws": AWSProvider,
}


def get_provider(name: str):
    cls = _REGISTRY.get(name)
    if not cls:
        raise ValueError(f"Unknown provider: {name}")
    return cls()


def get_all_enabled_providers():
    return [p() for p in _REGISTRY.values() if p().is_enabled()]
