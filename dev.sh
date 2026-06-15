#!/bin/bash

# Development helper script for the personal website

case "$1" in
    "serve" | "dev")
        echo "Starting development server..."
        uv run mkdocs serve
        ;;
    "build")
        echo "Building the site..."
        uv run mkdocs build
        ;;
    "deploy")
        echo "Building and deploying to GitHub Pages..."
        uv run mkdocs gh-deploy
        ;;
    "install")
        echo "Installing dependencies..."
        uv sync
        ;;
    "clean")
        echo "Cleaning build artifacts..."
        rm -rf site/
        ;;
    *)
        echo "Usage: $0 {serve|build|deploy|install|clean}"
        echo ""
        echo "Commands:"
        echo "  serve    - Start development server"
        echo "  build    - Build the static site"
        echo "  deploy   - Deploy to GitHub Pages"
        echo "  install  - Install dependencies"
        echo "  clean    - Clean build artifacts"
        exit 1
        ;;
esac
