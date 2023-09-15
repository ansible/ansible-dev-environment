"""Generate a dependency tree."""


from __future__ import annotations

from typing import TYPE_CHECKING, Union

from pip4a.tree import Tree
from pip4a.utils import collect_manifests


if TYPE_CHECKING:
    from pip4a.config import Config
    from pip4a.output import Output

ScalarVal = Union[bool, str, float, int, None]
JSONVal = Union[ScalarVal, list["JSONVal"], dict[str, "JSONVal"]]


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
        # pylint: disable=too-many-locals
        collections = collect_manifests(
            target=self._config.site_pkg_collections_path,
            venv_cache_dir=self._config.venv_cache_dir,
        )
        tree_dict: JSONVal = {c: {} for c in collections}
        if not isinstance(tree_dict, dict):
            msg = "Tree dict is not a dict."
            raise TypeError(msg)

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
                if not isinstance(target, dict):
                    msg = "Tree dict is not a dict."
                    raise TypeError(msg)

                target[dep] = tree_dict[dep]

            docs = collection["collection_info"].get("documentation")
            homepage = collection["collection_info"].get("homepage")
            repository = collection["collection_info"].get("repository")
            issues = collection["collection_info"].get("issues")
            link = docs or homepage or repository or issues or "http://ansible.com"
            if not isinstance(link, str):
                msg = "Link is not a string."
                raise TypeError(msg)
            links[collection_name] = link

        if self._config.args.verbose:
            tree = Tree(obj=tree_dict, term_features=self._config.term_features)
            tree.links = links
            rendered = tree.render()
            print(rendered)  # noqa: T201
            return

        pruned_tree_dict: JSONVal = {}
        if not isinstance(pruned_tree_dict, dict):
            msg = "Tree dict is not a dict."
            raise TypeError(msg)
        for collection_name in list(tree_dict.keys()):
            found = False
            for value in tree_dict.values():
                if not isinstance(value, dict):
                    msg = "Tree dict is not a dict."
                    raise TypeError(msg)
                if collection_name in value:
                    found = True
            if not found:
                pruned_tree_dict[collection_name] = tree_dict[collection_name]

        tree = Tree(obj=pruned_tree_dict, term_features=self._config.term_features)
        tree.links = links
        rendered = tree.render()
        print(rendered)  # noqa: T201
