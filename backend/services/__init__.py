"""Services package.

Individual services are imported directly by consumers to avoid
pulling in heavy dependencies (like ``obdtracker``) when only a
subset of services is needed (e.g., during testing).
"""
