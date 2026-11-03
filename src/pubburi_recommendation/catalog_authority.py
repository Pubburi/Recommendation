"""Explicit dispatch between container authority and isolated family-browse DEMO authority."""

from pubburi_recommendation.catalog_audit import AuditError, read_json
from pubburi_recommendation.source_catalog import load_source_catalog


def load_export_catalog(manifest, raw, receipt, curation, *, family_review=None):
    data, _ = read_json(curation)
    if data.get("algorithm") == "reviewed-source-family-browse-demo-v1":
        if family_review is None:
            raise AuditError("family_browse_source_review_required")
        from pubburi_recommendation.family_browse_catalog import load_family_browse_catalog

        return load_family_browse_catalog(manifest, raw, receipt, curation, family_review)
    if family_review is not None:
        raise AuditError("family_review_cannot_change_container_authority")
    return load_source_catalog(manifest, raw, receipt, curation)
