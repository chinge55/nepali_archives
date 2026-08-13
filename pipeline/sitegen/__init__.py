"""Maintainable, dependency-free static-site generation."""

from .context import BuildContext, BuildStats, OutputManifest, output_manifest

__all__ = ["BuildContext", "BuildStats", "OutputManifest", "output_manifest"]
