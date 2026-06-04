"""Plugin loader for stevedore-based storage client extensions."""

import stevedore

STORAGE_CLIENTS_NAMESPACE = "wattnet.storage.clients"


def _get_names(namespace: str) -> frozenset:
    """Get the names of the plug-ins in the specified namespace.

    :param namespace: The namespace to search for plug-ins
    :type namespace: str

    :return: The names of the plug-ins in the specified namespace
    :rtype: frozenset
    """
    mgr: stevedore.ExtensionManager = stevedore.ExtensionManager(namespace=namespace)
    return frozenset(mgr.names())


def _get_extensions(namespace: str) -> dict:
    """Get the extensions of the plug-ins in the specified namespace.

    :param namespace: The namespace to search for plug-ins
    :type namespace: str

    :return: The extensions of the plug-ins in the specified namespace
    :rtype: dict
    """
    mgr: stevedore.ExtensionManager = stevedore.ExtensionManager(
        namespace=namespace, propagate_map_exceptions=True
    )
    return dict(mgr.map(lambda ext: (ext.entry_point.name, ext.plugin)))


def get_storage_clients_names() -> frozenset:
    """Get the names of the storage clients.

    :return: The names of the energy clients
    :rtype: frozenset
    """
    return _get_names(STORAGE_CLIENTS_NAMESPACE)


def get_storage_clients_extensions() -> dict:
    """Get the extensions of the storage clients.

    :return: The extensions of the storage clients
    :rtype: dict
    """
    return _get_extensions(STORAGE_CLIENTS_NAMESPACE)
