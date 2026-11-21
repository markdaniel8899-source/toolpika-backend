#!/bin/bash
set -e

APP_ENV=test pytest tests/ -v --tb=short --cov=app --cov-report=term-missing
