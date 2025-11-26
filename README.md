# **mkdocs2notion**

A command-line tool that converts a directory of Markdown documents—optionally structured with `mkdocs.yml`—into a fully-organized Notion workspace.

This utility mirrors the publishing behavior of **MkDocs**, but targets **Notion pages** instead of a static site.

All parsing and conversion logic is implemented natively in this repository, with an adapter layer that can use **Ultimate Notion** (if installed) or a future Notion SDK integration.

---

## **Features**

* 🗂 **Publish entire Markdown folders to Notion**
* 📄 **Accurate Markdown → Notion block conversion**
* 📚 **Optional mkdocs.yml navigation support**
* 🔗 **Maintains hierarchical structure and ordering**
* 🆔 **Local file-path ↔ page-ID mapping for updates**
* 🛠 **Dry-run mode for testing without touching Notion**
* ⚙️ **Adapter layer** to support different Notion clients

---

## **Why This Exists**

Markdown is easy to write.
Notion is easy to share/control.

But getting a structured Markdown knowledge base into Notion—*and keeping it updated*—is hard.

`mkdocs2notion` solves that by:

* replicating MkDocs’ handling of directories, files, and nav trees,
* converting Markdown into rich Notion blocks,
* creating/updating pages while maintaining structure,
* allowing teams to turn entire docs folders into Notion workspaces.

---

## **Installation**

`mkdocs2notion` is not yet on PyPI (until the core APIs stabilize),
but you can install it locally:

```bash
pip install -e .
```

Or install from GitHub:

```bash
pip install git+https://github.com/mahbam42/mkdocs2notion
```

---

## **Basic Usage**

### **Push a directory to Notion**

```bash
mkdocs2notion push docs/
```

### **With mkdocs.yml navigation**

```bash
mkdocs2notion push docs/ --mkdocs mkdocs.yml
```

### **Dry run (see what would happen)**

```bash
mkdocs2notion dry-run docs/
```

---

## **Configuration**

### **Environment variables**

You will need a Notion API token:

```
NOTION_TOKEN=your-secret-token
```

Optional:

```
NOTION_PARENT_PAGE_ID=...   # where new pages should be created
```

---

## **How It Works**

`mkdocs2notion` processes content in stages:

### **1. Directory Loader**

* Walks the directory
* Reads Markdown files
* Extracts titles (frontmatter or H1)
* Generates metadata for each page

### **2. mkdocs.yml Navigation Loader** (optional)

* Reads `mkdocs.yml`
* Builds an ordered tree of sections/pages

### **3. Markdown Parser**

* Converts Markdown into internal block structures
* Converts those blocks into Notion-ready representations

### **4. Notion Adapter**

A thin abstraction around Notion operations (via Ultimate Notion or another SDK):

* create/update pages
* send block updates
* maintain parent-child relationships

You can swap the adapter without touching the logic.

---

## **Project Structure**

```
mkdocs2notion/
│
├── mkdocs2notion/
│   ├── markdown/
│   ├── loaders/
│   ├── notion/
│   ├── cli.py
│   └── runner.py
│
├── tests/
├── pyproject.toml
└── README.md
```

---

## **Roadmap**

* [ ] Core Markdown → Notion block converter
* [ ] Directory import with ID mapping
* [ ] mkdocs.yml → hierarchy builder
* [ ] Initial CLI (Typer-based)
* [ ] Add docs for block coverage
* [ ] Publish PyPI v0.2.0

---

## **Contributing**

See **`agents.md`** for strict guidelines on:

* development workflow
* linting + typing
* testing 
* commit rules
* agent behavior

Contributions are welcome—but must follow these standards to maintain reliability.

---

## **License**

MIT License.

