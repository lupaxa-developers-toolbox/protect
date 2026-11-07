<p align="center">
  <a href="https://github.com/lupaxa-developers-toolbox">
    <img src="https://raw.githubusercontent.com/the-lupaxa-project/brand-assets/master/logos/organisations/developers-toolbox/readme-logo.png" alt="Developers Toolbox" />
  </a>
</p>

<h1 align="center">Protect</h1>

Keep a sidecar copy of a file so you can edit locally and restore it
before committing. The library copies, restores, deletes, and reports
those sidecars. The `protect` command is the same four actions.

The PyPI name is `lupaxa-protect`. The import path is `lupaxa.protect`.
The console script is `protect`. `lupaxa` is a namespace package — there
is no `lupaxa/__init__.py`.

Public names: `protect`, `revert`, `clean`, `status`, `Config`,
`__version__`, `get_version()`.

## Install

```bash
pip install lupaxa-protect
```

Requires Python 3.10 or newer. There are no runtime dependencies.
`python -m lupaxa.protect` runs the same command.

## What it Does

A sidecar is the original name plus an extension. `notes.txt` becomes
`notes.txt.protect`. The default extension is `.protect`. `-e bak` and
a config `"ext": ".bak"` both mean `.bak`. The extension must start
with a dot and must not contain `/` or `\`.

Protect copies the file. An existing sidecar is left alone. If the
original is newer, the command warns and still skips the copy. `--update`
copies again only in that case. `--force` overwrites the sidecar even
when the sidecar is newer. Passing both makes `--force` win. A file that
already ends with the extension is never copied again.

Status prints one line per source file and writes nothing. `missing`
has no sidecar. `stale` means the original is newer. `newer` means the
sidecar is newer. `current` means the modification times match. The
report is printed even when the command is quiet.

Revert copies the sidecar back over the original. The write goes through
a temporary file, then replaces the original, so a crash does not leave
a half-written file. `--remove-backups` deletes the sidecar after a
successful restore.

Clean deletes sidecars and leaves the originals.

Revert and clean ask `Proceed? [y/N]` first. `-y`, a config `"yes": true`,
or `--dry-run` skips that question. Empty input and any answer other
than `y` or `yes` cancel the run. `--dry-run` prints the plan and
changes nothing. Pass `--verbose` to print each action. Without that
flag the command is quiet. `-q` requests that same quiet output.

One of `-p`, `-v`, `-c`, or `-s` is required, unless you are only
printing or validating config. Those four actions cannot be combined.
Paths may be files, directories, or globs. With no paths, the command
scans a base directory: `-d` if you passed it, otherwise `dir` from the
config, otherwise the working directory. Subdirectories are entered only
with `-R`, `"recursive": true`, and not `--no-recursive`.

Dotfiles, and anything inside a dot-directory such as `.github`, are
skipped unless `--include-hidden` or `"include_hidden": true` is set.

## Library

```python
from pathlib import Path

from lupaxa.protect import clean, protect, revert, status

protect(
    files=[Path("notes.txt")],
    ext=".protect",
    dry=False,
    quiet=True,
    force=False,
    update=False,
)
status(files=[Path("notes.txt")], ext=".protect", check=False)
revert(
    pairs=[(Path("notes.txt.protect"), Path("notes.txt"))],
    dry=False,
    quiet=True,
    remove_backups=False,
    yes=True,
)
clean(
    pairs=[(Path("notes.txt.protect"), Path("notes.txt"))],
    dry=False,
    quiet=True,
    yes=True,
)
```

`protect` returns `0` when every copy succeeds and `1` when one fails.
`update=True` refreshes a sidecar only when the original is newer.
`force=True` overwrites an existing sidecar. `revert` and `clean` return
`2` when the confirmation is declined. `yes=True` skips that prompt.
`quiet=True` suppresses the action lines. `status` prints the report and
returns `0`, or `1` when a file cannot be read. `check=True` also returns
`1` when a sidecar is missing or the original is newer. A sidecar that is
newer than the file still returns `0`.

## Command Line

```bash
protect -p notes.txt
protect --verbose -p notes.txt
protect -q -p notes.txt
protect -p --update notes.txt
protect -p --force notes.txt
protect -p -R .
protect -p --no-recursive .
protect -p --set docs
protect -s .
protect --check .
protect -v notes.txt
protect -v --remove-backups --yes notes.txt
protect -c --yes notes.txt
protect --verbose -p --dry-run .
protect --print-config
protect --validate-config
protect --version
```

| Flag                | Meaning                                                                                  |
| ------------------- | ---------------------------------------------------------------------------------------- |
| `paths`             | Files, directories, or globs. The base directory is used when omitted.                   |
| `-p`, `--protect`   | Copy each file to a sidecar.                                                             |
| `-v`, `--revert`    | Restore each file from its sidecar.                                                      |
| `-c`, `--clean`     | Delete sidecars.                                                                         |
| `-s`, `--status`    | Print missing, stale, newer, and current. Change nothing.                                |
| `-R`, `--recursive` | Enter subdirectories. `--no-recursive` turns a config true off.                          |
| `-e`, `--ext`       | Sidecar extension. Default `.protect`.                                                   |
| `-d`, `--dir`       | Base directory when no paths are given.                                                  |
| `-q`, `--quiet`     | Print only warnings and errors. This is the default.                                     |
| `--verbose`         | Print each action. Cannot be combined with `-q`.                                         |
| `--check`           | With status, exit `1` when a sidecar is missing or the original is newer.                |
| `--force`           | Overwrite an existing sidecar. `--no-force` turns a config true off.                     |
| `--update`          | Copy again only when the original is newer. `--no-update` turns this off.                |
| `--remove-backups`  | After a successful revert, delete the sidecar. `--no-remove-backups` turns this off.     |
| `-y`, `--yes`       | Skip the revert and clean confirmation. `--no-yes` turns a config true off.              |
| `--dry-run`         | Print the plan and change nothing.                                                       |
| `--include-hidden`  | Include dotfiles and files inside dot-directories. `--no-include-hidden` turns this off. |
| `--set`             | Named set from `.protect.config`. Repeat to combine sets.                                |
| `--config`          | Read this config file instead of discovering one.                                        |
| `--no-config`       | Do not load a config file.                                                               |
| `--ignore`          | Add an ignore pattern. Repeat for more than one.                                         |
| `--ignore-file`     | Read patterns from a file. Repeat for more than one.                                     |
| `--no-ignore`       | Do not load `.protectignore`. Built-in ignores still apply.                              |
| `--print-config`    | Print the resolved settings as JSON and exit `0`.                                        |
| `--validate-config` | Check the config and ignore files, print JSON, then exit.                                |
| `--version`         | Print `protect x.y.z` and exit `0`.                                                      |

| Result                                                                                         | Exit |
| ---------------------------------------------------------------------------------------------- | ---- |
| Action finished                                                                                | `0`  |
| Some files failed, status could not read a file, or `--check` found a missing or stale sidecar | `1`  |
| Bad arguments, or you cancelled                                                                | `2`  |
| The base path is not a directory                                                               | `2`  |
| `--validate-config` found errors                                                               | `2`  |

## See Sidecar State

`-s` and `--status` compare each source file with its sidecar and print
the result. Nothing is copied, restored, or deleted. `--dry-run` does
not change this report. `-q` and `--verbose` do not hide it either.

```bash
protect -s .
protect -s -R docs
protect -s notes.txt
```

| Line                  | Meaning                                 |
| --------------------- | --------------------------------------- |
| `missing PATH`        | The source has no sidecar.              |
| `stale PATH`          | The original is newer than the sidecar. |
| `newer PATH`          | The sidecar is newer than the original. |
| `current PATH`        | The modification times are the same.    |
| `No files to report.` | The scan found no source files.         |

`PATH` is the resolved source path. The same selection rules as protect
apply: the base directory, paths, sets, recursion, hidden files, and
ignore patterns. A sidecar whose original is gone is not listed.

Exit `0` when every file was read. Exit `1` when a file cannot be
read. That file is omitted and an `ERROR` line is written to stderr.

`--check` uses the same report and then exits `1` when any line is
`missing` or `stale`. `newer` and `current` still exit `0`. `protect
--check` is the same as `protect -s --check`. `--check` cannot be
combined with protect, revert, or clean.

## Refresh a Newer Original

Protect leaves an existing sidecar in place unless you ask it to copy
again.

| How you run it                     | Existing sidecar                               |
| ---------------------------------- | ---------------------------------------------- |
| `-p`                               | Kept. A newer original produces a warning.     |
| `-p --update`, or `"update": true` | Replaced only when the original is newer.      |
| `-p --force`, or `"force": true`   | Replaced, including when the sidecar is newer. |
| `--force` and `--update` together  | `--force` wins and the sidecar is replaced.    |

The warning for a newer original is:

```text
WARNING: backup exists for 'notes.txt' and the original is newer. Use --update to refresh it, or --force to overwrite.
```

`--update` does not copy when the sidecar is newer or the times match.
`--no-update` keeps that skip even when the config says `"update": true`.
A failed stat warns and the copy goes ahead.

## Turn a Setting Off

These settings can be set in `.protect.config`. The matching flag
replaces that value for one run. The `--no-` form sets it to false.

| Setting          | Turn on             | Turn off              |
| ---------------- | ------------------- | --------------------- |
| `recursive`      | `-R`, `--recursive` | `--no-recursive`      |
| `include_hidden` | `--include-hidden`  | `--no-include-hidden` |
| `force`          | `--force`           | `--no-force`          |
| `update`         | `--update`          | `--no-update`         |
| `remove_backups` | `--remove-backups`  | `--no-remove-backups` |
| `yes`            | `-y`, `--yes`       | `--no-yes`            |

```bash
protect -p --no-recursive .
```

With `"recursive": true` in the config, that command stays in the base
directory. Leave both flags off and the config value is used.
`--dry-run`, `-q`, and `--verbose` are command-line only. `--no-config` and
`--no-ignore` skip a file. They do not turn a boolean setting off.

## Keep Sidecars Out of Git

A sidecar is a local copy. Add its extension to the repository
`.gitignore` so Git does not commit it.

```gitignore
*.protect
```

That matches `notes.txt.protect` in any directory. If `-e` or the config
`ext` uses another suffix, ignore that suffix instead. `.bak` uses
`*.bak`.

## Configuration

Discovery order:

1. `--config FILE`, when you pass it.
2. `.protect.config`, walking up from the working directory or from `-d`, stopping at your home directory.
3. `~/.protect/protect.config`.
4. Built-in defaults.

The file is JSON. Whole-line `//` comments, trailing `//` comments, and
`/* ... */` blocks are stripped before parsing. `--no-config` skips this
file. A boolean flag on the command line replaces the config value.
`--recursive` turns the setting on. `--no-recursive` turns it off.
Omitting the flag keeps the config value, so `"recursive": true` still
enters subdirectories when you do not pass `-R` or `--no-recursive`.

| Key              | Meaning                                                             |
| ---------------- | ------------------------------------------------------------------- |
| `ext`            | Sidecar extension. Must start with `.`. Default `.protect`.         |
| `recursive`      | Enter subdirectories. Default `false`.                              |
| `include_hidden` | Include dotfiles and dot-directories. Default `false`.              |
| `force`          | Overwrite an existing sidecar during protect. Default `false`.      |
| `update`         | Refresh a sidecar only when the original is newer. Default `false`. |
| `remove_backups` | Delete the sidecar after a successful revert. Default `false`.      |
| `yes`            | Skip revert and clean prompts. Default `false`.                     |
| `dir`            | Base directory when `-d` and paths are omitted. Default `.`.        |
| `ignore`         | Extra ignore patterns. A string or a list of strings.               |
| `sets`           | Named groups of files, directories, or globs.                       |

Unknown keys are reported as warnings. They do not fail validation.

```json
{
  "ext": ".protect",
  "recursive": true,
  "include_hidden": false,
  "force": false,
  "update": false,
  "remove_backups": false,
  "yes": false,
  "dir": ".",
  "ignore": ["*.log"],
  "sets": {
    "docs": ["README.md", "docs"]
  }
}
```

## Ignore Files

`.protectignore` is discovered the same way as the config: walk upward
to your home directory, then `~/.protect/protectignore`. `--no-ignore`
skips that search. `--ignore-file` reads the files you name and does
not also load the discovered file. `--no-config` does not skip the
ignore file.

Patterns are one per line. Blank lines and lines starting with `#` are
dropped. A pattern matches the file name or the path relative to the
base directory. `*` matches across slashes. There is no `!` exception.
A trailing slash is part of the pattern, so `__pycache__/` does not
match a directory whose name is `__pycache__`.

Built-in patterns always apply. Config `ignore`, `.protectignore`, and
`--ignore` are added to them. Nothing in those files can bring a
built-in pattern back.

```text
.git
.hg
.svn
.idea
.vscode
__pycache__
.mypy_cache
.pytest_cache
.DS_Store
node_modules
dist
build
target
.tox
.coverage
coverage*
*.coverage
*.pyc
*.pyo
*.lock
*.log
venv
.venv
.env
.env.*
```

## Named Sets

`sets` groups paths under a name. `--set` selects one. Repeat the flag
to combine groups. Extra paths on the command are added to the set.
An unknown name is skipped, with a warning.

```bash
protect --verbose -p --set docs --set ops
```

```json
{
  "sets": {
    "docs": ["README.md", "docs"],
    "ops": ["scripts"]
  }
}
```

A set that points inside a dot-directory, such as `.github`, is skipped
unless hidden files are included.

## Check the Config

`--validate-config` checks the config that would be loaded and every
ignore file used for the run. It prints JSON and does not copy or
delete files. Exit `0` means the files are valid. Exit `2` means the
config is missing when you passed `--config`, the file is not JSON, a
value has the wrong type, or an ignore file cannot be read. Unknown
keys and a missing discovered config are warnings. Warnings still exit
`0`.

`--print-config` prints the resolved settings: which config and ignore
files were loaded, the merged ignore list, and the options a protect,
revert, or clean run would use. It exits `0`.

```bash
protect --validate-config
protect --print-config
protect --validate-config --config .protect.config
```

## Development

```bash
make init
make python-install-dev
make python-check
```

<a href="https://github.com/the-lupaxa-project">
    <img src="https://raw.githubusercontent.com/the-lupaxa-project/brand-assets/master/logos/components/footer-for-child-orgs.svg" alt="The Lupaxa Project Footer" width="100%" />
</a>
