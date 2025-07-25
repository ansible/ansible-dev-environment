# Ansible Development Environment

A pip-like install for Ansible collections.

## Communication

- Join the Ansible forum:
  - [Get Help](https://forum.ansible.com/c/help/6): get help or help others.
    Please add appropriate tags if you start new discussions.
  - [Social Spaces](https://forum.ansible.com/c/chat/4): gather and interact
    with fellow enthusiasts.
  - [News & Announcements](https://forum.ansible.com/c/news/5): track
    project-wide announcements including social events.
  - [Bullhorn newsletter](https://docs.ansible.com/ansible/devel/community/communication.html#the-bullhorn):
    used to announce releases and important changes.

For more information about communication, see the
[Ansible communication guide](https://docs.ansible.com/ansible/devel/community/communication.html).

## Features

- Promotes an "ephemeral" development approach
- Ensures the current development environment is isolated
- Install all collection python requirements
- Install all collection test requirements
- Checks for missing system packages
- Symlinks the current collection into the current python interpreter's
  site-packages
- Install all collection collection dependencies into the current python
  interpreter's site-packages
- Uses `uv env` instead of python's venv when available to boost performance.
  Can be disabled with `SKIP_UV=1`

By placing collections into the python site-packages directory they are
discoverable by ansible as well as python and pytest.

## Usage

### Setting up a development environment

{{ install_from_adt("ansible-dev-environment") }}

```bash
pip3 install ansible-dev-environment --user
```

```
$ git clone <collection_repo>
$ cd <collection_repo>
$ ade install -e .\[test] --venv .venv
INFO: Found collection name: network.interfaces from /home/bthornto/github/network.interfaces/galaxy.yml.
INFO: Creating virtual environment: /home/bthornto/github/network.interfaces/venv
INFO: Virtual environment: /home/bthornto/github/network.interfaces/venv
INFO: Using specified interpreter: /home/bthornto/github/network.interfaces/venv/bin/python
INFO: Requirements file /home/bthornto/github/network.interfaces/requirements.txt is empty, skipping
INFO: Installing python requirements from /home/bthornto/github/network.interfaces/test-requirements.txt
INFO: Installing ansible-core.
INFO: Initializing build directory: /home/bthornto/github/network.interfaces/build
INFO: Copying collection to build directory using git ls-files.
INFO: Running ansible-galaxy to build collection.
INFO: Running ansible-galaxy to install collection and it's dependencies.
INFO: Removing installed /home/bthornto/github/network.interfaces/venv/lib64/python3.11/site-packages/ansible_collections/network/interfaces
INFO: Symlinking /home/bthornto/github/network.interfaces/venv/lib64/python3.11/site-packages/ansible_collections/network/interfaces to /home/bthornto/github/network.interfaces
WARNING: A virtual environment was specified but has not been activated.
WARNING: Please activate the virtual environment:
source venv/bin/activate
```

### Tearing down the development environment

```
$ ade uninstall ansible.scm
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

`ade --help`

`ade install --help`

`ade uninstall --help`
