#!/usr/bin/python3
# vim: set expandtab shiftwidth=4 softtabstop=4:

def main():
    # Process arguments
    import getopt, sys
    try:
        opts, args = getopt.getopt(sys.argv[1:], "dhP:q")
    except getopt.GetoptError as e:
        print("Error: %s" % str(e), file=sys.stderr)
        print_help(sys.stderr)
        raise SystemExit(1)
    debug = False
    quiet = False
    packages = []
    for opt, val in opts:
        if opt == "-d":
            debug = True
        elif opt == "-P":
            packages.append(val)
        elif opt == "-q":
            quiet = True
        elif opt == "-h":
            print_help(sys.stdout)
            raise SystemExit(0)
    if len(args) == 0:
        print_help(sys.stderr)
        raise SystemExit(1)
    if not packages:
        from . import filter_collectors, report_ood
        ood_packages = out_of_date_packages()
        packages = [pkg["name"] for pkg in ood_packages]
        if not packages:
            if not quiet:
                print("No out-of-date packages found", file=sys.stderr)
            raise SystemExit(0)
        report_ood(ood_packages)

    # Collect import information from Python source files
    from . import collect
    collectors = []
    single = len(args) == 1
    for directory in args:
        collectors.extend(collect(directory, quiet, single))

    # Identify which files imported which packages
    from . import filter_collectors, report_importers
    print("\nImported by:")
    for pkg in packages:
        importers = filter_collectors(collectors, pkg)
        report_importers(importers, pkg)

def print_help(f):
    import sys, os.path
    program = os.path.basename(sys.argv[0])
    print("Usage:", "python3 -m", __package__, "[-d]", "[-q]", "[-P package]",
          "directory...", file=f)
    print("         if -P is not used, check for out-of-date packages", file=f)
    print("         -P may be repeated multiple times to "
          "check several packages", file=f)
    print("   or:", "python3 -m", __package__, "[-h]", file=f)

def out_of_date_packages():
    # Ideally, there would be a pip API for getting this information
    # but since they clearly do not want to define the API, we use
    # pip as a command
    import sys, subprocess, json
    cp = subprocess.run([sys.executable, "-m", "pip", "list",
                         "--outdated", "--format=json"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE)
    if cp.returncode != 0:
        raise ValueError("pip terminated with exit status %d" % cp.returncode)
    pkgs = json.loads(cp.stdout.decode("utf-8"))
    return pkgs

if False:
    # Debug test against this source file
    def main():
        import sys
        c = Collector(sys.argv[0])
        print(c.module_names)

if False:
    # Debug test for out-of-date packages from pip
    def main():
        print(out_of_date_packages())

if __name__ == "__main__":
    main()