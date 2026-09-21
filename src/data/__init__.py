"""Accès aux données du lac : lecture, sélection, découpage."""

from .dataset import load_silver, select_features, split_par_moteur

# `__all__` déclare l'interface publique du paquet. Sans lui, ces trois
# imports passent pour inutilisés (F401) : un réexport n'est jamais
# consommé dans le fichier qui le porte.
__all__ = ["load_silver", "select_features", "split_par_moteur"]
