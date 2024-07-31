"""Generate a dependency tree."""

from __future__ import annotations

from typing import TYPE_CHECKING, Union, cast

from ansible_dev_environment.tree import Tree
from ansible_dev_environment.utils import builder_introspect, collect_manifests


if TYPE_CHECKING:
    from ansible_dev_environment.config import Config
    from ansible_dev_environment.output import Output

ScalarVal = bool | str | float | int | None
JSONVal = ScalarVal | list["JSONVal"] | dict[str, "JSONVal"]

TreeWithReqs = dict[str, Union[list[str], "TreeWithReqs"]]
TreeWithoutReqs = dict[str, "TreeWithoutReqs"]


class TreeMaker:
    """Generate a dependency tree."""

    def __init__(self: TreeMaker, config: Config, output: Output) -> None:
        """Initialize the object.

        Args:
            config: The application configuration.
            output: The application output object.
        """
        self._config = config
        self._output = output

    def run(self: TreeMaker) -> None:  # noqa: C901, PLR0912, PLR0915
        """Run the command."""
        builder_introspect(self._config, self._output)

        with self._config.discovered_python_reqs.open("r") as reqs_file:
            python_deps = reqs_file.read().splitlines()

        collections = collect_manifests(
            target=self._config.site_pkg_collections_path,
            venv_cache_dir=self._config.venv_cache_dir,
        )
        tree_dict: TreeWithoutReqs = {c: {} for c in collections}

        links: dict[str, str] = {}
        for collection_name, collection in collections.items():
            err = f"Collection {collection_name} has malformed metadata."
            if not isinstance(collection["collection_info"], dict):
                self._output.error(err)
                continue
            if not isinstance(collection["collection_info"]["dependencies"], dict):
                self._output.error(err)
                continue

            for dep in collection["collection_info"]["dependencies"]:
                if not isinstance(dep, str):
                    err = f"Collection {collection_name} has malformed dependency."
                    self._output.error(err)
                    continue
                target = tree_dict[collection_name]
                target[dep] = tree_dict[dep]

            docs = collection["collection_info"].get("documentation")
            homepage = collection["collection_info"].get("homepage")
            repository = collection["collection_info"].get("repository")
            issues = collection["collection_info"].get("issues")
            fallback = "https://ansible.com"
            link = repository or homepage or docs or issues or fallback
            if not isinstance(link, str):
                err = f"Collection {collection_name} has malformed repository metadata."
                self._output.error(err)
                link = fallback
            links[collection_name] = link

            if self._config.args.verbose >= 1:
                add_python_reqs(
                    tree_dict=cast(TreeWithReqs, tree_dict),
                    collection_name=collection_name,
                    python_deps=python_deps,
                )
        green: list[str] = []
        if self._config.args.verbose >= 1:
            green.append("python requirements")
            for line in python_deps:
                if "#" not in line:
                    green.append(line.strip())
                green.append(line.split("#", 1)[0].strip())

        more_verbose = 2
        if self._config.args.verbose >= more_verbose:
            tree = Tree(obj=cast(JSONVal, tree_dict), term_features=self._config.term_features)
            tree.links = links
            tree.green.extend(green)
            rendered = tree.render()
            print(rendered)  # noqa: T201
        else:
            pruned_tree_dict: TreeWithoutReqs = {}
            for collection_name in tree_dict:
                found = False
                for value in tree_dict.values():
                    if collection_name in value:
                        found = True
                if not found:
                    pruned_tree_dict[collection_name] = tree_dict[collection_name]

            tree = Tree(
                obj=cast(JSONVal, pruned_tree_dict),
                term_features=self._config.term_features,
            )
            tree.links = links
            tree.green.extend(green)
            rendered = tree.render()
            print(rendered)  # noqa: T201

        if self._config.args.verbose >= 1:
            msg = "Only direct python dependencies are shown."
            self._output.info(msg)
            hint = "Run `pip show <pkg>` to see indirect dependencies."
            self._output.hint(hint)


def add_python_reqs(
    tree_dict: TreeWithReqs,
    collection_name: str,
    python_deps: list[str],
) -> None:
    """Add Python dependencies to the tree.

    Args:
        tree_dict: The tree dict.
        collection_name: The collection name.
        python_deps: The Python dependencies.

    Raises:
        TypeError: If the tree dict is not a dict.
    """
    collection = tree_dict[collection_name]
    if not isinstance(collection, dict):
        msg = "Did you really name a collection 'python requirements'?"
        raise TypeError(msg)

    deps = []
    for dep in sorted(python_deps):
        if "#" in dep:
            name, comment = dep.split("#", 1)
        else:
            name = dep
            comment = ""
        if collection_name in comment:
            deps.append(name.strip())

    collection["python requirements"] = deps
