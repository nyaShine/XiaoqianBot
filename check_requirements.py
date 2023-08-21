import pkg_resources
import sys
import warnings


def main():
    requirements_file = sys.argv[1]
    with open(requirements_file, "r") as f:
        required_packages = [
            line.strip().split("#")[0].strip() for line in f.readlines()
        ]

    installed_packages = {pkg.key: pkg.version for pkg in pkg_resources.working_set}

    missing_packages = []
    for required_package in required_packages:
        if not required_package:  # 跳过空行
            continue
        pkg = pkg_resources.Requirement.parse(required_package)
        if pkg.key not in installed_packages:
            missing_packages.append(str(pkg))
        elif pkg_resources.parse_version(installed_packages[pkg.key]) not in pkg.specifier:
            warnings.warn(f"{pkg.key}的已安装版本与所需版本不匹配。")

    if missing_packages:
        print("缺少的 Package：")
        print(", ".join(sorted(missing_packages)))
        sys.exit(1)
    else:
        print("所有 Packages 都已安装。")


if __name__ == "__main__":
    main()
