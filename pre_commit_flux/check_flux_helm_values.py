import glob
import os.path as path
import subprocess
import sys
import tempfile
from shlex import quote

import yaml

errors: list = []


def main():
    repos = _buildRepoMap()
    for arg in sys.argv[1:]:
        try:
            _validateFile(arg, repos)
        except Exception as ex:
            _collectErrors({"source": arg, "message": f"{type(ex).__name__} {ex.args}"})
    if len(errors) > 0:
        _printErrors()
        exit(1)

def _isSupportedRepo(definition):
    return _isSupportedChartRepo(definition) or _isSupportedChartRefRepo(definition)

def _isSupportedChartRepo(definition):
    return _isSupportedKind(definition, ["HelmRepository"])

def _isSupportedChartRefRepo(definition):
    return _isSupportedKind(definition, ["OCIRepository"])

def _isHelmRelease(definition):
    return _isSupportedKind(definition, ["HelmRelease"])

def _isSupportedKind(definition, supportedKinds):
    return definition and "kind" in definition and definition["kind"] in supportedKinds

def _buildRepoMap():
    repos = {}
    for file in glob.glob("./**/*.yaml", recursive=True):
        with open(file) as f:
            try:
                for definition in yaml.load_all(f, Loader=yaml.SafeLoader):
                    if _isSupportedChartRepo(definition):
                        repoName = definition["metadata"]["name"]
                        repos[repoName] = [definition["spec"]["url"], None]
                    elif _isSupportedChartRefRepo(definition):
                        repoName = definition["metadata"]["name"]
                        if "ref" not in definition["spec"] or "tag" not in definition["spec"]["ref"]:
                            continue
                        repos[repoName] = [definition["spec"]["url"], definition["spec"]["ref"]["tag"]]
                    else:
                        continue
                    if not _isSupportedRepo(definition):
                        continue
            except Exception:
                continue

    return repos


def _validateFile(fileToValidate, repos):
    with open(fileToValidate) as f:
        for definition in yaml.load_all(f, Loader=yaml.SafeLoader):
            if not _isHelmRelease(definition):
                continue

            chartName = None
            try:
                chartSpec = definition["spec"]["chart"]["spec"]
                if not _isSupportedChartRepo(chartSpec["sourceRef"]):
                    continue
                chartName = chartSpec["chart"]
                chartVersion = chartSpec["version"]
                chartUrl = repos[chartSpec["sourceRef"]["name"]][0]
                if chartUrl.startswith("oci://"):
                    if not chartUrl.endswith("/"):
                        chartUrl += "/"
                    chartUrl += chartName
                    chartName = None
            except KeyError as e:
                if definition["spec"]["chartRef"]:
                    chartSpec = definition["spec"]["chartRef"]
                    if not _isSupportedChartRefRepo(chartSpec):
                        continue
                    chartUrl, chartVersion = repos[chartSpec["name"]]
                else:
                    raise e

            with tempfile.TemporaryDirectory() as tmpDir:
                with open(path.join(tmpDir, "values.yaml"), "w") as valuesFile:
                    if "spec" in definition and "values" in definition["spec"]:
                        yaml.dump(definition["spec"]["values"], valuesFile)

                command = f"helm pull {quote(chartUrl)} --version {quote(chartVersion)}"
                if chartName:
                    command += f" {quote(chartName)}"
                
                res = subprocess.run(
                    command,
                    shell=True,
                    cwd=tmpDir,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
                if res.returncode != 0:
                    _collectErrors(
                        {"source": "helm pull", "message": f"\n{res.stdout}"}
                    )
                    continue

                res = subprocess.run(
                    "helm lint -f values.yaml *.tgz",
                    shell=True,
                    cwd=tmpDir,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
                if res.returncode != 0:
                    _collectErrors(
                        {"source": "helm lint", "message": f"\n{res.stdout}"}
                    )


def _collectErrors(error):
    errors.append(error)


def _printErrors():
    for i in errors:
        print(f"[ERROR] {i['source']}: {i['message']}")


if __name__ == "__main__":
    main()
