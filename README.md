# ansible-dev-environment

A development environment management tool for Ansible content development that
provides isolated workspaces for development. `ansible-dev-environment` (ade)
manages virtual environments, collection installation and removal, and Python
dependency resolution to ensure consistent, reproducible development
environments.

## Overview

`ansible-dev-environment` (ade) provides comprehensive collection development
environment management by:

- Creating isolated virtual environments for development
- Installing and removing collections with full dependency tracking
- Resolving and installing collection Python dependencies from
  `requirements.txt` and `test-requirements.txt`
- Installing collections in editable mode with symlinks for active development
- Managing development dependencies like `ansible-dev-tools`
- Providing configurable workspace isolation

While `ansible-galaxy` efficiently manages collection installation and
dependencies, it does not handle Python package dependencies that collections
may require. `ade` complements this by ensuring all Python requirements are
properly managed within isolated environments.

Collections are installed into Python's site-packages directory, making them
discoverable by both Ansible and Python tooling including pytest.

## Philosophy

Modern Ansible collection development requires isolation to prevent conflicts
between projects with different dependency requirements. Each collection project
may require:

- Different Python package versions (e.g., `requests==2.25.0` vs
  `requests==2.31.0`)
- Different Ansible core versions (`ansible-core>=2.15` vs `ansible-core<2.17`)
- Different collection dependencies that may have conflicting requirements
- Different Python interpreter versions

`ade` addresses these challenges by creating project-specific virtual
environments where both Python packages and Ansible collections are installed.
This approach offers several advantages:

- **Complete isolation**: Each project has its own dependency space
- **Reproducible environments**: Consistent development setup across team
  members
- **Safe experimentation**: Virtual environments can be destroyed and recreated
  without affecting other projects
- **Version control friendly**: Virtual environments are typically excluded from
  git repositories, keeping repos clean
- **Python version flexibility**: Each project can specify its required Python
  version

By installing collections into the virtual environment's site-packages (rather
than global Ansible paths), collections become part of the disposable
development environment, eliminating the "dependency hell" common in shared
collection spaces.

### Collection Search Path Pollution

A critical issue in Ansible collection development is workspace pollution caused
by Ansible's collection search path behavior. Ansible searches for collections
in this priority order:

1. Paths in `ANSIBLE_COLLECTIONS_PATHS` environment variable
2. `~/.ansible/collections` (user collections directory)
3. `/usr/share/ansible/collections` (system collections directory)
4. Virtual environment site-packages (when properly configured)

When collections exist in higher-priority locations, they **override**
collections in your virtual environment, leading to:

- **Silent version conflicts**: Your venv may contain `community.general 5.8.0`,
  but Ansible uses `community.general 4.2.0` from `~/.ansible/collections`
- **Inconsistent behavior**: Code works on one developer's machine but fails on
  another due to different global collections
- **Debugging nightmares**: Test failures that appear unrelated to your changes,
  caused by different collection versions being loaded
- **Development confusion**: Modified collection code has no effect because
  Ansible loads an older version from a global location

For example, if you're developing `community.crypto` and have an older version
installed globally:

```bash
# Your development setup
ls .venv/lib/python3.11/site-packages/ansible_collections/community/crypto/
# Contains your latest changes

# But Ansible finds this first
ls ~/.ansible/collections/ansible_collections/community/crypto/
# Contains an older version that overrides your work
```

This is why `ade` provides isolation modes:

- **`cfg` mode**: Creates `ansible.cfg` with `collections_path = .` to
  prioritize the current workspace
- **`restrictive` mode**: Fails fast if global collections are detected, forcing
  cleanup
- **`none` mode**: Allows pollution (not recommended for development)

Proper isolation ensures that `ansible-playbook`, `ansible-test`, and `pytest`
all use the exact collection versions installed in your virtual environment,
making development predictable and reproducible.

## Installation

Install using `uv` (recommended):

```bash
uv tool install ansible-dev-environment
```

Alternative installation methods:

```bash
pip install ansible-dev-environment
# or
pipx install ansible-dev-environment
```

## Quick Start

Create an isolated development environment for a collection:

```bash
git clone https://github.com/namespace/collection-name
cd collection-name
ade install -e . --venv .venv
```

## Commands

```
$ ade --help
usage: ade [-h] [--ansi | --no-ansi] [--lf LOG_FILE]
           [--ll {notset,debug,info,warning,error,critical}] [--la {true,false}]
           [--uv | --no-uv] [-v] [-V]
            ...

A pip-like ansible collection installer.

Commands:
  check        Check installed collections
  inspect      Inspect installed collections
  list         List installed collections
  tree         Generate a dependency tree
  install      Install a collection
  uninstall    Uninstall a collection
```

### Installation Options

```
$ ade install --help
usage: ade install [-h] [--venv <directory>] [--cpi] [--ssp] [-r REQUIREMENT]
                   [--acv ANSIBLE_CORE_VERSION] [-e] [-p PYTHON] [--seed | --no-seed]
                   [--im {restrictive,cfg,none}] [--uv | --no-uv] [-v]
                   [collection_specifier ...]

Options:
  --venv <directory>        Target virtual environment (default: .venv)
  -e, --editable           Install in editable mode (development)
  -r, --requirement <file> Install from requirements file
  -p, --python             Python interpreter for virtual environment (version, name, or path)
  --seed / --no-seed       Install ansible-dev-tools (default: true)
  --im, --isolation-mode   Isolation mode (choices: restrictive, cfg, none)
  --acv                    Ansible core version constraint
  --uv / --no-uv           Use uv package manager if available (default: true)
```

### Install with Specific Python Version

```bash
# Use Python 3.11 specifically
ade install -e . --venv .venv --python python3.11

# Use Python by version number
ade install -e . --venv .venv --python 3.12

# Use specific Python path
ade install -e . --venv .venv --python /usr/bin/python3.10
```

## Isolation Modes

`ade` provides three isolation modes to prevent collection conflicts:

- **`cfg`** (default): Creates/updates `ansible.cfg` in the current directory
  with `collections_path = .` to isolate the workspace
- **`restrictive`**: Exits if collections are found in system locations
  (`~/.ansible/collections`, `/usr/share/ansible/collections`)
- **`none`**: No isolation (not recommended for development)

## Usage Examples

### Basic Collection Development

Install a collection in editable mode:

```bash
ade install -e . --venv .venv
```

Example output:

```
Info: uv is available and will be used instead of venv/pip
Info: Found collection name: example.demo from ./galaxy.yml
Note: Created virtual environment: .venv
Info: Installing ansible-dev-tools
Info: Installing python requirements from ./requirements.txt
Info: Installing python requirements from ./test-requirements.txt
Info: Installing ansible-core
Info: Installing collection dependencies
Info: Installing local collection: example.demo
```

### Install from Requirements File

```bash
ade install -r requirements.yml --venv .venv
```

### Install Specific Ansible Core Version

```bash
ade install -e . --venv .venv --acv 2.18.0
```

### List Installed Collections

```bash
ade list --venv .venv
```

### Check Collection Dependencies

```bash
ade tree --venv .venv
```

## Environment Variables

Configure behavior via environment variables:

```bash
export ADE_PYTHON=python3.12           # Python interpreter
export ADE_UV=false                    # Disable uv usage
export ADE_ISOLATION_MODE=cfg          # Set isolation mode
export ADE_VERBOSE=2                   # Verbosity level
export ADE_ANSIBLE_CORE_VERSION=2.18.0 # Ansible core version
```

## Virtual Environment Management

`ade` can create virtual environments using either Python's built-in `venv` or
`uv` (when available). When `uv` is detected, it's used automatically for faster
environment creation and package installation.

To activate the created environment:

```bash
source .venv/bin/activate  # Linux/macOS
```

## Configuration

### ansible.cfg Integration

With `cfg` isolation mode (default), `ade` creates or updates `ansible.cfg`:

```ini
[defaults]
collections_path = .
```

This ensures Ansible only discovers collections from the current workspace.

### Collection Requirements

`ade` processes these requirement files when present:

- `requirements.txt` - Runtime Python dependencies
- `test-requirements.txt` - Development/testing dependencies
- `requirements.yml` - Collection dependencies (processed by ansible-galaxy)

## Troubleshooting

### Environment Isolation Issues

If using `restrictive` mode and seeing isolation errors:

```bash
# Remove system collections
sudo rm -rf /usr/share/ansible/collections

# Clear user collections
rm -rf ~/.ansible/collections

# Unset collection path variables
unset ANSIBLE_COLLECTIONS_PATHS ANSIBLE_COLLECTION_PATH
```

### Virtual Environment Issues

Ensure the virtual environment is activated after installation:

```bash
source .venv/bin/activate
```

## Related Tools

- `ansible-galaxy`: Collection management and installation
- `ansible-dev-tools`: Development tooling suite for Ansible content creators
- `uv`: Fast Python package installer and resolver
