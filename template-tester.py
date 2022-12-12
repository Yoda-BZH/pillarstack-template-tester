#!/usr/bin/env python3

import os
import sys
import copy
import glob
import yaml
import jinja2
import difflib
import colorama
import datetime
import argparse
import importlib
import jsonpath_rw
import configparser
import salt.utils.templates

no_color = False
verbose = False
__opts__ = {}

def mergedicts(dict1, dict2_):
  dict2 = dict2_.copy()
  d2ks = dict2.copy().keys()
  for d2k in d2ks:
    if d2k == "__*":
      for kk in dict1.keys():
        dict2[kk] = dict2["__*"]
        dict2[kk].update(dict1[kk])
  if "__*" in dict2:
    dict2.pop("__*")

  for k in set(dict1.keys()).union(dict2.keys()):
    if k in dict1 and k in dict2:
      if isinstance(dict1[k], dict) and isinstance(dict2[k], dict):
        yield (k, dict(mergedicts(dict1[k], dict2[k])))
      elif isinstance(dict1[k], list) and isinstance(dict2[k], list):
        try:
          dict1[k].sort()
          dict2[k].sort()
        except:
          pass
        try:
          yield (k, sorted(list(set(dict1[k] + dict2[k]))))
        except Exception as e:
          try:
            res = dict1[k] + [i for i in dict2[k] if i not in dict1[k]]
            try:
              res = sorted(res)
            except:
              pass
            yield (k, res)
          except Exception as ee:
            raise ee
      else:
        # If one of the values is not a dict, you can't continue merging it.
        # Value from second dict overrides one in first and we move on.
        yield (k, dict2[k])
        # Alternatively, replace this with exception raiser to alert you of value conflicts
    elif k in dict1:
      yield (k, dict1[k])
    else:
      yield (k, dict2[k])

def check_dict_not_in_dict(needle, haystack):
  for key, value in needle.items():
    if value is None:
      r = key not in haystack
      if not r:
        del(haystack[key])
      return r
    if key not in haystack:
      return True
    return check_dict_not_in_dict(needle[key], haystack[key])
  return False

def write_output(dirname, filename, content):
    output_dir = os.path.join(dirname, os.path.dirname(filename))
    basename = os.path.basename(filename)
    os.makedirs(output_dir, exist_ok=True)
    f = open(os.path.join(output_dir, basename), 'w', encoding="utf-8")
    f.write(content)
    f.close()

class SaltObject():
    callables = {}
    modules = {}
    def __call__(self, *args, **kwargs):
        funcname = args[0]
        if funcname in self.callables:
            return self.callables[funcname]
        if args[1] != None:
            return args[1]
        return None

    def inject(self, data):
        # print("injecting")
        # print(data)
        self.callables = data

    def add_call(self, modulename, funcname, **kwargs):
        # print("call to {}.{} added".format(modulename, funcname), kwargs)
        self.modules[modulename] = {'func': funcname, 'kwargs': kwargs}

    def __getitem__(self, name, **kwargs):
        # print("in getitemname", name, "callable", self.callables, "kwargs", kwargs)
        if name in self.modules:
            modulename = "salt.modules.{}".format(name.split('.')[0])
            try:
                # print("trying to import {}".format(modulename))
                r = importlib.import_module(modulename)
                # print(type(r))
                # print(r, name)
                func = r.__getattribute__(name.split('.')[1])
                # print("got func", func)
                return func
            except Exception:
                return self.callables[funcname]()
        # else:
        #     print("name not in self.modules", namedtuple)

        if name in self.callables:
            r = SaltObject()
            r.inject(self.callables[name])
            return r
            #print(name, "not in", self.callables)
        # else:
        #     print("name not in self.callables", name)
        return None

def run_tests(f, config, outputdir=""):
    if sys.version_info.major >= 3 and sys.version_info.minor >= 6:
        current_dt = datetime.datetime.now().isoformat(timespec='microseconds')
    else:
        current_dt = datetime.datetime.now().isoformat()
    print("[{}] Parsing {} ...".format(current_dt, f.name))
    test_data = f.read()
    test_data_yaml = yaml.load(test_data, Loader = yaml.SafeLoader)

    if not test_data_yaml:
        print("Error: Test file {} is empty.".format(f.name))
        return(1)

    target_template_filenames = sorted(glob.glob(test_data_yaml['file']))

    if len(target_template_filenames) == 0:
        print("{} does not match a file".format(test_data_yaml['file']))
        return(1)

    excluded_files = []
    if "file_exclude" in test_data_yaml:
        excluded_files = sorted(glob.glob(test_data_yaml["file_exclude"]))
        for excluded_file in excluded_files:
            print("{} skipping {} ...".format(" "*28, excluded_file))

        target_template_filenames = set(target_template_filenames) - set(excluded_files)

    main_return_value = 0

    for target_template_filename in target_template_filenames:
        if target_template_filename != test_data_yaml['file']:
            print("{} against {} ...".format(" "*28, target_template_filename))
        if 'file' in test_data_yaml:
            try:
                target_template_file = open(target_template_filename, 'r', encoding="utf-8")
                target_template_data = target_template_file.read()
            except Exception as e:
                print("Error: File '{}' not found for test file {}".format(test_data_yaml['file'], f.name))
                print(e)
                return(1)
        elif 'wrapper' in test_data_yaml:
            print(test_data_yaml)
            target_template_data = test_data_yaml['wrapper']
            print(target_template_data)

        saltobject = SaltObject()
        context = {
            'opts': {
              'jinja_env': {},
              'jinja_sls_env': {},
            },
            'sls': {},
            'saltenv': {},
            'salt': saltobject,
            '__salt__': saltobject,
        }
        if '__call' in test_data_yaml['variables']:
            for modulename, funcname in test_data_yaml['variables']['__call'].items():
                saltobject.add_call(modulename, funcname)
            context['__opts__'] = context['opts']
            globals()['__opts__'] = context['opts']
        if 'salt' in test_data_yaml['variables']:
            saltobject.inject(test_data_yaml['variables'].pop('salt'))
            # print("injected")
        context.update(test_data_yaml['variables'])
        if verbose:
            print("### Given:")
            print(yaml.dump(context, Dumper = yaml.Dumper))
        #print(target_template_data)
        # print("final context", context, "opts", __opts__)

        try:
            template_data = salt.utils.templates.render_jinja_tmpl(tmplstr = target_template_data, context = context, tmplpath = "pillars/")
        except Exception as e:
            print("Unable to parse the file {} with the provided variables: {}".format(test_data_yaml['file'], context))
            raise e
            return(1)

        try:
            yaml_from_template = yaml.load(template_data.strip(), Loader = yaml.SafeLoader)
        except Exception as e:
            if 'content' in test_data_yaml:
              #print("Continuing with raw-non-yaml content")
              yaml_from_template = template_data.strip()
            else:
              print("Unable to load generated yaml content, is it real yaml ?")
              print("------------------")
              print(template_data.strip())
              print("------------------")
              print('Error was:')
              raise e

        #if verbose:
        #  expected_result_yaml = yaml.dump(expected_results, Dumper = yaml.Dumper)
        #  result_yaml          = yaml.dump(yaml_from_template, Dumper = yaml.Dumper)

        return_value = 0

        if 'expected' in test_data_yaml:
            expected_results = test_data_yaml['expected']
            if outputdir:
                write_output(outputdir, f.name, template_data)

            if expected_results != yaml_from_template:
                #print("BAD")
                return_value = 1

        elif 'content' in test_data_yaml:
          expected_results = test_data_yaml['content'].strip()
          current_result = template_data.strip()
          if current_result != expected_results:
              return_value = 1

        elif 'content_partial' in test_data_yaml:
          expected_results = test_data_yaml['content_partial'].strip()
          current_result = template_data.strip()
          #print('------------')
          #print(current_result)
          #print('------------')
          #print(expected_results)
          #print('------------')
          if expected_results not in current_result:
              return_value = 1

        elif 'expected_partial' in test_data_yaml:
            expected_results = copy.deepcopy(test_data_yaml['expected_partial'])
            if outputdir:
                write_output(outputdir, f.name, template_data)

            original = yaml_from_template.copy()
            merged = dict(mergedicts(original, expected_results))
            if merged != yaml_from_template:
                expected_results = merged
                return_value = 1

        elif 'expected_absent' in test_data_yaml:
            expected_results = test_data_yaml['expected_absent']
            if outputdir:
                write_output(outputdir, f.name, template_data)
            original = yaml_from_template.copy()
            merged = dict(mergedicts(expected_results, original))
            r = check_dict_not_in_dict(expected_results, original)

            if not r:
                expected_results = merged
                return_value = 1

        elif 'check_list' in test_data_yaml:
            test_data_item = test_data_yaml["check_list"]
            for key_to_search, conditions in test_data_item.items():
                items = [match.value  for match in get_item_from_pattern(key_to_search, yaml_from_template.copy())]
                if len(items) == 0:
                    print("No item found in this file")
                    return_value = 1
                    continue
                if not isinstance(items[0], list):
                    expected_results = "{} to be a {}".format(key_to_search, "list")
                    return_value = 1
                    continue
                if "morethan" in test_data_item[key_to_search]:
                    value = test_data_item[key_to_search]["morethan"]
                    expected_results = "{} to be a list of {} {}".format(key_to_search, "morethan", value)
                    if len(items[0]) < value:
                        return_value = 1
                elif "equalto" in test_data_item[key_to_search]:
                    value = test_data_item[key_to_search]["equalto"]
                    expected_results = "{} to be a list of {} {}".format(key_to_search, "equalto", value)
                    if len(items[0]) == value:
                        return_value = 1
                elif "lessthan" in test_data_item[key_to_search]:
                    value = test_data_item[key_to_search]["lessthan"]
                    expected_results = "{} to be a list of {} {}".format(key_to_search, "lessthan", value)
                    if len(items[0]) > value:
                        return_value = 1
                else:
                    print("this token is not found")
                    return_value = 1

        elif 'check_string' in test_data_yaml:
            test_data_item = test_data_yaml["check_string"]
            for key_to_search, conditions in test_data_item.items():
                items = [match for match in get_item_from_pattern(key_to_search, yaml_from_template.copy())]
                if not isinstance(items[0].value, str):
                    expected_results = "{} to be a {}".format(key_to_search, "string")
                    return_value = 1
                    continue
                if "notempty"  in test_data_item[key_to_search]:
                    value = test_data_item[key_to_search]["notempty"]
                    expected_results = "{} to be a {}".format(key_to_search, "not empty", value)
                    if not value:
                        return_value = 1
                elif "stringnotempty"  in test_data_item[key_to_search]:
                    value = test_data_item[key_to_search]["stringnotempty"]
                    expected_results = "{} to be a {}".format(key_to_search, "string")
                    if value == "":
                        return_value = 1
                #elif "stringiscontained"  in test_data_item[key_to_search]:
                #    value = test_data_item[key_to_search]["stringiscontained"]
                #    expected_results = "{} to be a string of {} {}".format(key_to_search, "stringiscontained", value)
                #    if value not in items[0].value:
                #        return_value = 1
                elif "contains" in test_data_item[key_to_search]:
                    value = test_data_item[key_to_search]["contains"]
                    expected_results = "{} to be a string which contains {}".format(key_to_search, value)
                    if value not in items[0].value:
                        return_value = 1
                elif "contains_key" in test_data_item[key_to_search]:
                    value = str(items[0].context.path)
                    expected_results = "{} to be a string ({}) containing {}".format(items[0].full_path, items[0].value, value)
                    yaml_from_template = "{} to be a string ({})".format(items[0].full_path, items[0].value)
                    #print(value, items[0].value, type(value), type(items[0].value), value in items[0].value)

                    if value not in items[0].value:
                        return_value = 1
                elif "equalto"  in test_data_item[key_to_search]:
                    value = test_data_item[key_to_search]["equalto"]
                    expected_results = "{} to be a string of {} {}".format(key_to_search, "equalto", value)
                    if value not in items[0].value:
                        return_value = 1
                else:
                    print("this token is not found")
                    return_value = 1

        elif 'check_int' in test_data_yaml:
            test_data_item = test_data_yaml["check_int"]
            for key_to_search, conditions in test_data_item.items():
                items = [match for match in get_item_from_pattern(key_to_search, yaml_from_template.copy())]
                yaml_from_template = "{} = {}".format(items[0].full_path, items[0].value)
                if not isinstance(items[0].value, int):
                    expected_results = "{} to be a {}".format(key_to_search, "int")
                    return_value = 1
                    continue
                if "equalto"  in test_data_item[key_to_search]:
                    value = test_data_item[key_to_search]["equalto"]
                    expected_results = "{} = {}".format(items[0].full_path, value)
                    if value != items[0].value:
                        return_value = 1
                elif "greaterthan"  in test_data_item[key_to_search]:
                    value = test_data_item[key_to_search]["greaterthan"]
                    expected_results = "{} > {}".format(items[0].full_path, value)
                    if value > items[0].value:
                        return_value = 1
                elif "lowerthan"  in test_data_item[key_to_search]:
                    value = test_data_item[key_to_search]["lowerthan"]
                    expected_results = "{} < {}".format(items[0].full_path, value)
                    if value < items[0].value:
                        return_value = 1
                else:
                    print("this token '{}' is not found".format(conditions))
                    return_value = 1
        elif 'check_bool' in test_data_yaml:
            test_data_item = test_data_yaml["check_bool"]
            for key_to_search, conditions in test_data_item.items():
                items = [match for match in get_item_from_pattern(key_to_search, yaml_from_template.copy())]
                yaml_from_template = "{} = {}".format(items[0].full_path, items[0].value)
                if not isinstance(items[0].value, bool):
                    expected_results = "{} to be a {}".format(key_to_search, "bool")
                    return_value = 1
                    continue
                if "is"  in test_data_item[key_to_search]:
                    value = test_data_item[key_to_search]["is"]
                    expected_results = "{} = {}".format(items[0].full_path, value)
                    if value != items[0].value:
                        return_value = 1
                else:
                    print("this token '{}' is not found".format(conditions))
                    return_value = 1
        else:
            print("No condition to test.")
            return_value = 1
            main_return_value = 1
            continue

        if verbose:
            expected_result_yaml = yaml.dump(expected_results, Dumper=yaml.SafeDumper)
            result_yaml          = yaml.dump(yaml_from_template, Dumper=yaml.SafeDumper)
            print("### I was expecting:")
            print(expected_result_yaml)
            print("### But I got:")
            print(result_yaml)


        if return_value == 1:
            main_return_value = 1
            if 'content' in test_data_yaml:
                expected_result_yaml = expected_results
                result_yaml = current_result
            else:
                expected_result_yaml = yaml.dump(expected_results, Dumper=yaml.SafeDumper)
                result_yaml = yaml.dump(yaml_from_template, Dumper=yaml.SafeDumper)

            yml_diff = difflib.unified_diff(
                expected_result_yaml.splitlines(keepends=True),
                result_yaml.splitlines(keepends=True),
                fromfile="expected",
                tofile="generated",
            )

            if no_color:
                sys.stdout.writelines(yml_diff)
            # sys.stdout.writelines(difflib.unified_diff(
            #   expected_result_yaml.splitlines(keepends=True),
            #   result_yaml.splitlines(keepends=True),
            #   fromfile="expected",
            #   tofile="generated",
            # ))
            else:
                for line in yml_diff:
                    if line.startswith('+'):
                        sys.stdout.write(colorama.Fore.GREEN + line + colorama.Fore.RESET)
                    elif line.startswith('-'):
                        sys.stdout.write(colorama.Fore.RED + line + colorama.Fore.RESET)
                    elif line.startswith('^'):
                        sys.stdout.write(colorama.Fore.BLUE + line + colorama.Fore.RESET)
                    else:
                        sys.stdout.write(line)

    return(main_return_value)

def get_item_from_pattern(pattern, data):
    expression = jsonpath_rw.parse(pattern)
    return expression.find(data)

def stats_add_test(stats, pillar, testfile):
    if pillar not in stats:
        stats[pillar] = {'count': 0, 'tests': []}

    stats[pillar]['count'] += 1
    stats[pillar]['tests'].append(testfile)

    return stats


def do_stats(test_files, config):
    stats = {}
    ignored_files = config['ignore']['files'].split("\n")
    for pillar_file in glob.glob('pillars/**/*.yml', recursive=True):
        must_be_ignored = False
        for ignored in ignored_files:
            if ignored in pillar_file:
                #print("Skipping ignored {} because {}".format(pillar_file, ignored))
                must_be_ignored = True
                break
        if must_be_ignored:
            continue
        if "pillars/customers/" in pillar_file:
            continue
        if pillar_file == "tests/template-tester.yml":
            continue
        if os.path.islink(pillar_file):
            continue
        if os.path.islink(os.path.dirname(pillar_file)):
            continue
        stats[pillar_file] = {'count': 0, 'tests': []}

    for test_file in test_files:
        if test_file == "tests/template-tester.yml":
            continue
        test_data = open(test_file).read()
        test_data_yaml = yaml.load(test_data, Loader=yaml.SafeLoader)
        tested_files = sorted(glob.glob(test_data_yaml['file']))
        for tested_file in tested_files:
            stats = stats_add_test(stats, tested_file, test_file)

    number_of_tested_file = 0
    number_of_files = 0
    number_of_tests = 0

    for stat_pillar_file in sorted(stats):
        number_of_test = "#" * stats[stat_pillar_file]['count'] or "-"
        line = "{}: {} tests {}".format(stat_pillar_file, stats[stat_pillar_file]['count'], number_of_test)
        if no_color is False:
            if stats[stat_pillar_file]['count'] == 0:
                color = colorama.Fore.RED
            else:
                color = colorama.Fore.GREEN
            line = color + line + colorama.Fore.RESET
        print(line)
        if stats[stat_pillar_file]['count']:
            number_of_tests += stats[stat_pillar_file]['count']
            number_of_tested_file += 1
        number_of_files += 1

    percent_of_tested_files = (100 * number_of_tested_file) / number_of_files
    print("number of files: {}, number of tested files: {} by {} tests".format(number_of_files, number_of_tested_file, number_of_tests))
    print("Coverage: {}%".format(round(percent_of_tested_files, 2)))


if __name__ == "__main__":
    #a = {'foo': 'foo', 'bar': 'bar'}
    #print(check_dict_not_in_dict({'baz': None}, a))
    #sys.exit(0)
    parser = argparse.ArgumentParser()
    parser.add_argument(
      'file',
      type=str,
      help="Test only the provided files/directory",
      default=[],
      nargs="*"
    )
    #parser.add_argument('-f', '--file', help="Test only the provided file")
    parser.add_argument(
      '-n', '--no-color',
      help="no color mode",
      default=False,
      action="store_true"
    )
    parser.add_argument(
      '-s', '--stats',
      help="statistics",
      default=False,
      action="store_true"
    )
    parser.add_argument(
      '-v', '--verbose',
      help="Enable verbose mode for all checks",
      default=False,
      action="store_true"
    )
    parser.add_argument(
      '-S', '--stop',
      help="Stop testing at first error",
      default=False,
      action="store_true",
    )
    parser.add_argument(
      '-w', '--write-dir',
      help="Write generated files in directory",
      default="",
      type=str
    )
    args = parser.parse_args()
    no_color = args.no_color
    verbose = args.verbose

    config_path = os.path.dirname(os.path.realpath(__file__))
    config = configparser.ConfigParser()
    config.read("{}/{}".format(config_path, 'template-tester.conf'))

    if 'DEFAULT' in config and 'test_dir' in config['DEFAULT']:
        default_test_dir = config['DEFAULT']['test_dir']
    else:
        default_test_dir = "tests"

    if args.write_dir and not os.path.isdir(args.write_dir):
        os.mkdir(args.write_dir)

    return_value = 0

    test_files = []
    if type(args.file) == list and args.file:
      for args_file in args.file:
        if os.path.isdir(args_file):
          print(
            'is dir',
            "{}/{}".format(
              args_file.rstrip('/'),
              "*.yml"
            )
          )
          test_files += sorted(glob.glob(
              "{}/**/{}".format(args_file.rstrip('/'), '*.yml'),
              recursive=True
          ))
        else:
          test_files += [args_file]
    else:
        test_files = sorted(glob.glob(
            '{}/**/*.yml'.format(default_test_dir),
            recursive=True
        ))

    if args.stats:
        do_stats(test_files, config)
        sys.exit(0)

    failed_tests = []
    for testfile in test_files:
        if testfile == "tests/template-tester.yml":
            continue
        test_return_value = run_tests(
            open(testfile, 'r', encoding="utf-8"),
            config,
            outputdir=args.write_dir
        )
        return_value |= test_return_value
        if test_return_value == 1:
            failed_tests.append(testfile)
            if args.stop:
              break

    if return_value == 0:
        print("All checks are ok.")
    else:
        print("The following tests failed:")
        for failed_test in failed_tests:
            print("* {}".format(failed_test))
    sys.exit(return_value)
