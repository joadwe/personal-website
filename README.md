# Joshua Welsh - Personal Website
This is the source code for my personal website, built with [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/).## AboutThis website showcases my research work, publications, talks, and resources in the field of translational medicine, with a focus on:- Extracellular vesicle research- Flow cytometry development and standardization- Biomedical instrumentation- Software development for reproducible research## Development### Prerequisites- Python 3.8+- pip
### Setup

1. Clone this repository:
   ```bash
   git clone https://github.com/joshuawelsh/personal-website.git
   cd personal-website
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Start the development server:
   ```bash
   mkdocs serve
   ```

4. Open your browser to `http://127.0.0.1:8000`

### Building

To build the static site:

```bash
mkdocs build
```

The built site will be in the `site/` directory.

## Deployment

This site is automatically deployed to GitHub Pages using GitHub Actions when changes are pushed to the `main` branch.

## Structure

```
.
├── docs/                 # Documentation source files
│   ├── index.md         # Home page
│   ├── about.md         # About page
│   ├── publications.md  # Publications list
│   ├── talks.md         # Talks and presentations
│   └── resources.md     # Tools and resources
├── mkdocs.yml           # MkDocs configuration
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## License

© 2025 Joshua Welsh. All rights reserved.

## Contact

- Email: joshua.welsh@bd.com
- LinkedIn: [joshua-welsh-phd](https://linkedin.com/in/joshua-welsh-phd)
- ORCID: [0000-0003-1746-1279](https://orcid.org/0000-0003-1746-1279)
