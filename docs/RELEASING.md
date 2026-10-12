# Publishing a release

1. Set the same version in `custom_components/barbs_erse/manifest.json`, `custom_components/barbs_erse/const.py`, and `pyproject.toml`.
2. Add a matching `## <version>` section with release notes to `CHANGELOG.md` and update the card resource version in the README.
3. Commit and push those changes to the default branch, and wait for CI to pass.
4. In GitHub, open **Actions → Publish release → Run workflow**. Enter the version without a `v` prefix, such as `0.1.2`.

The workflow verifies the version metadata and changelog, reruns the release validation checks, then creates a `v<version>` tag and a GitHub Release from the current default-branch commit. It uses the matching changelog section as the release notes. It stops if the version metadata disagrees, the changelog section is missing, or the tag already exists.
