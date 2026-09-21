"""Accès au lac de données MinIO : système de fichiers et chemins."""

from .lake import LAYERS, get_lake_filesystem, lake_path

__all__ = ["LAYERS", "get_lake_filesystem", "lake_path"]
