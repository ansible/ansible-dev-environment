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

    def __init__(self, config: Config, output: Output) -> None:
        """Initialize the object.

        Args:
            config: The application configuration.
            output: The application output object.
        """
        self._config = config
        self._output = output

    def run(self) -> None:
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
        self._process_collections(collections, tree_dict, python_deps, links)
        green = self._build_green_list(python_deps)

        more_verbose = 2
        if self._config.args.verbose >= more_verbose:
            tree = Tree(obj=cast("JSONVal", tree_dict), term_features=self._config.term_features)
            tree.links = links
            tree.green.extend(green)
            rendered = tree.render()
            print(rendered)  # noqa: T201
        else:
            pruned_tree_dict = self._prune_tree(tree_dict)

            tree = Tree(
                obj=cast("JSONVal", pruned_tree_dict),
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

    def _process_collections(
        self,
        collections: dict[str, dict[str, JSONVal]],
        tree_dict: TreeWithoutReqs,
        python_deps: list[str],
        links: dict[str, str],
    ) -> None:
        """Process collections to build tree dict and extract links.

        Args:
            collections: The collections to process.
            tree_dict: The tree dict to populate with dependencies.
            python_deps: The Python dependencies list.
            links: The links dict to populate with collection links.
        """
        for collection_name, collection in collections.items():
            err = f"Collection {collection_name} has malformed metadata."
            ci = collection.get("collection_info")
            if not isinstance(ci, dict):
                self._output.error(err)
                continue
            deps = ci.get("dependencies")
            if not isinstance(deps, dict):
                self._output.error(err)
                continue

            for dep in deps:
                if not isinstance(dep, str):
                    err = f"Collection {collection_name} has malformed dependency."
                    self._output.error(err)
                    continue
                target = tree_dict[collection_name]
                target[dep] = tree_dict[dep]

            docs = ci.get("documentation")
            homepage = ci.get("homepage")
            repository = ci.get("repository")
            issues = ci.get("issues")
            fallback = "https://ansible.com"
            link = repository or homepage or docs or issues or fallback
            if not isinstance(link, str):
                err = f"Collection {collection_name} has malformed repository metadata."
                self._output.error(err)
                link = fallback
            links[collection_name] = link

            if self._config.args.verbose >= 1:
                add_python_reqs(
                    tree_dict=cast("TreeWithReqs", tree_dict),
                    collection_name=collection_name,
                    python_deps=python_deps,
                )

    def _build_green_list(self, python_deps: list[str]) -> list[str]:
        """Build the green list from python dependencies.

        Args:
            python_deps: The Python dependencies list.

        Returns:
            The green list.
        """
        green: list[str] = []
        if self._config.args.verbose >= 1:
            green.append("python requirements")
            green.extend(line.split("#", 1)[0].strip() for line in python_deps)
        return green

    def _prune_tree(self, tree_dict: TreeWithoutReqs) -> TreeWithoutReqs:
        """Prune the tree dict to only root collections.

        Args:
            tree_dict: The tree dict to prune.

        Returns:
            The pruned tree dict.
        """
        pruned_tree_dict: TreeWithoutReqs = {}
        for collection_name in tree_dict:
            found = False
            for value in tree_dict.values():
                if collection_name in value:
                    found = True
            if not found:
                pruned_tree_dict[collection_name] = tree_dict[collection_name]
        return pruned_tree_dict


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
