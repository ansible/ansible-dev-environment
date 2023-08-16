# pipac

A pip-like install for ansible collections.

## Features

- Promotes an "ephemeral" development approach
- Ensures the current development environment is isolated
- Install all collection python requirements
- Install all collection test requirements
- Checks for missing system packages
- Symlinks the current collection into the current python interpreter's site-packages
- Install all collection collection dependencies into the current python interpreter's site-packages

By placing collections into the python site-packages directory they are discoverable by ansible as well as python and pytest.

## Usage

### Setting up a development environment

```
$ git clone <collection_repo>
$ cd collection_repo
$ python -m venv venv
$ source venv/bin/activate
$ pip install pipac
$ pipac install -e .[test]
INFO     Found collection name: ansible.scm from /home/bthornto/github/ansible.scm/galaxy.yml.
INFO     Requirements file /home/bthornto/github/ansible.scm/requirements.txt is empty, skipping
INFO     Installing python requirements from /home/bthornto/github/ansible.scm/test-requirements.txt
INFO     Initializing build directory: /home/bthornto/github/ansible.scm/build
INFO     Running ansible-galaxy to build collection.
INFO     Running ansible-galaxy to install collection and it's dependencies.
INFO     Removing installed /home/bthornto/github/ansible.scm/venv/lib64/python3.11/site-packages/ansible_collections/ansible/scm
INFO     Symlinking /home/bthornto/github/ansible.scm/venv/lib64/python3.11/site-packages/ansible_collections/ansible/scm to /home/bthornto/github/ansible.scm
```

### Tearing down the development environment

```
$ pipac uninstall ansible.scm
INFO     Found collection name: ansible.scm from /home/bthornto/github/ansible.scm/galaxy.yml.
INFO     Requirements file /home/bthornto/github/ansible.scm/requirements.txt is empty, skipping
INFO     Uninstalling python requirements from /home/bthornto/github/ansible.scm/test-requirements.txt
INFO     Removed ansible.utils: /home/bthornto/github/ansible.scm/venv/lib64/python3.11/site-packages/ansible_collections/ansible/utils
INFO     Removed ansible.utils*.info: /home/bthornto/github/ansible.scm/venv/lib64/python3.11/site-packages/ansible_collections/ansible.utils-2.10.3.info
INFO     Removed ansible.scm: /home/bthornto/github/ansible.scm/venv/lib64/python3.11/site-packages/ansible_collections/ansible/scm
INFO     Removed collection namespace root: /home/bthornto/github/ansible.scm/venv/lib64/python3.11/site-packages/ansible_collections/ansible
INFO     Removed collection root: /home/bthornto/github/ansible.scm/venv/lib64/python3.11/site-packages/ansible_collections
```

## Help

```
$ pipac --help
usage: pipac [-h] [--verbose] {install,uninstall} ...

A pip-like ansible collection installer.

options:
  -h, --help           show this help message and exit
  --verbose            Increase output verbosity.

subcommands:
  valid subcommands

  {install,uninstall}  additional help
```

```
$ pipac install --help
usage: pipac install [-h] [-e] collection_specifier

positional arguments:
  collection_specifier  Collection to install.

options:
  -h, --help            show this help message and exit
  -e, --editable        Install editable.

Usage:
        pipac install .
        pipac install -e .
        pipac install -e .[test]
        python -m pipac install ansible.utils
```

````
$ pipac uninstall --help
usage: pipac uninstall [-h] collection_specifier

positional arguments:
  collection_specifier  Collection to uninstall.

options:
  -h, --help            show this help message and exit

Usage:
        pipac install .
        pipac install -e .
        pipac install -e .[test]
        python -m pipac install ansible.utils```
````
