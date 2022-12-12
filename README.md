# Pillarstack-template-tester

Salt pillarstack converts jinja+yaml code to plain yaml code.

This tools let you test the jinja code, and compare the output with an expected
output.

# Requirements

The following python modules are required:

* jinja2 (python3-jinja2)
* difflib (provided by python3)
* colorama (python3-colorama)
* argparse (provided by python3)
* importlib (provided by python3)
* jsonpath_rw (provided by python3-jsonpath-rw)
* configparser (provided by python3)
* salt.utils.template, generally provided by the `salt-common` package

# Options

```
  -h, --help            show this help message and exit
  -n, --no-color        no color mode
  -s, --stats           statistics
  -v, --verbose         Enable verbose mode for all checks
  -S, --stop            Stop testing at first error
  -w WRITE_DIR, --write-dir WRITE_DIR
                        Write generated files in directory
```

The option `-h` / `--help` display the help, and all available options.

The option `-n` / `--no-color` deactivate the use of color in the output.

The option `-s` / `--stats` computes the code coverage.

The option `-v` / `--verbose` set the script to verbose mode. Every test shows
the input variables, the complete expected and current outputs

The option `-S` / `--stop` stops the script at the first test error. If not
set, the script continues and shows every failed test at the end.

The option `-w` / `--write-dir` write every test output to a dirctory. This
let the possibility to use yamllint to check the yaml validity of the generated
code.


## Creating a new test

By default, all tests are stored in the `tests/` directory.

It is recommended to recreate the `pillar/` directory inside the `tests/`
directory.

It is adviced to name every test with the file tests + a brief description of
the tests.

Exemple, to test the file `pillar/global/myfile.yml`, a test file could be
`tests/pillar/global/myfile_testing-with-debian.yml`. Testing the same file
against redhat could be `tests/pillar/global/myfile_testing-with-redhat.yml`.


A test has 3 main keys :

* `file` the file to be tested
* `variables` Input variables nedeed to run the test. There are required
  variables and optionnals vars.
* A test name. See below

## Input file

The field `file` contains the filename to be tested, from the root directory of
the project.

Example:

The test file is `tests/pillar/global/directory_test1.yml`:

```yaml
file: pillar/global/directory.yml
```

## Input variables

Some variables are required to be defined :

* `pillar`: Contents of the salt pillar dictionnary
* `__grains__`: Contents of the salt grains dictionnary. Depending of your
  stack, it may be required to use `grains` instead


Some variables that can be used :

* `stack`: the special salt variable containing all previously defined
  variables.
* Any salt variable assumed to be already defined.


Example:

```
variables:
  pillar: {}
  __grains__: {}
```

```
variables:
  pillar:
    server_id:
      foo: bar
  __grains__:
    oscodename: bullseye
    os: Debian
    mem_total: 2048
    num_cpus: 2
```

## Available tests names

### Testing the yaml content/structure

#### expected

The generated yaml must be exactly identical to the ouput provided

Example:
```
file: pillar/global/directory.yml
variables:
  pillar: {}
  __grains__: {}
expected:
  foo:
    bar:
      baz: "this is baz"
      quux:
        this: "this
        is: "is"
        quux: "really quux"
```

#### expected_partial

The generated yaml must contains the output provided. The rest is not tester

Example:
```
file: pillar/global/directory.yml
variables:
  pillar: {}
  __grains__: {}
expected_partial:
  foo:
    bar:
      quux:
        is: "is"
```

#### expected_absent

The generated yaml must not contains the provided output

Example, the key "quux" must not be present in "foo":
```
file: pillar/global/directory.yml
variables:
  pillar: {}
  __grains__: {}
expected_absent:
  foo:
    quux: ~
```

### Testing the string content

#### content

The generated string must be exactly identical to the output provided

Example:
```
file: pillar/config.cfg
variables:
  pillar: {}
  __grains__: {}
content: |
  global/*.yml
  debian/*.yml
  redhat/*.yml
  cleanup/*.yml
```

#### content_partial

The generated string must contains the output provided

Example:
```
file: pillar/config.cfg
variables:
  pillar: {}
  __grains__: {}
content: |
  global/*.yml
```

### Checking specific values with wildcard and list indexes

The following tests can tests multiple values with wildcard or test specific
values in a list with index access.

The value to test must use the jsonpath format
(https://pypi.org/project/jsonpath-rw/)

Examples:
* `foo.bar.*`: all keys under `foo:bar:`
* `foo.bar.*.value`: all `value` field of every key under `foo:bar`
* `foo.bar.[*].value`: all `value` field for every entry of `foo:bar` list
* `foo.bar.[5].value`: all `value` field for the 6th entry of `foo:bar` list

#### check_list

The generated list must satisfy the provided requirement.

The requirements can be :
`
* `morethan
* `equalto`
* `lessthan`

Example, every list under `foo:bar` (foo:bar:list1, foo:bar:list2, etc) must
have at least 5 elements :
```
file: pillar/global/directory.yml
variables:
  pillar: {}
  __grains__: {}
check_list:
  foo.bar.*:
    morethan: 5
```


Example, every list under `foo:bar` (foo:bar:list1, foo:bar:list2, etc) must
have exactly 7 elements :
```
file: pillar/global/directory.yml
variables:
  pillar: {}
  __grains__: {}
check_list:
  foo.bar.*:
    equalto: 7
```


Example, every list under `foo:bar` (foo:bar:list1, foo:bar:list2, etc) must
have at least 5 elements :
```
file: pillar/global/directory.yml
variables:
  pillar: {}
  __grains__: {}
check_list:
  foo.bar.*:
    morethan: 5
```

#### check_string

The value must be a string-type.

The generated string(s) must satisfy the provided requirement.

The requirement can be :

* `stringnotempty`
* `contains`
* `equalto`


Example, the field "foo:bar:qux:is" must not be an empty string:
```
file: pillar/global/directory.yml
variables:
  pillar: {}
  __grains__: {}
check_string:
  foo.bar.quux.is:
    stringnotempty: ~
```

Example, the field "foo:bar:qux:quux" must contains "really":
```
file: pillar/global/directory.yml
variables:
  pillar: {}
  __grains__: {}
check_string:
  foo.bar.quux.quux:
    contains: "really"
```

Example, the field "foo:bar:qux:is" must be exactly the string "is":
```
file: pillar/global/directory.yml
variables:
  pillar: {}
  __grains__: {}
check_string:
  foo.bar.quux.is:
    equalto: "is"
```


#### check_int

The value must be an integer.

The generated integer must satisfy the provided requirement.

The requirement can be:

* `equalto`
* `greaterthan`
* `lowerthan`

Example, the value of "foo:bar:number" must be exactly `123`:
```
file: pillar/global/directory.yml
variables:
  pillar: {}
  __grains__: {}
check_int:
  foo.bar.number:
    equalto: 123
```

Example, the value of "foo:bar:number" must be greater `100`:
```
file: pillar/global/directory.yml
variables:
  pillar: {}
  __grains__: {}
check_int:
  foo.bar.number:
    greaterthan: 100
```

Example, the value of "foo:bar:number" must be lower than `200`:
```
file: pillar/global/directory.yml
variables:
  pillar: {}
  __grains__: {}
check_int:
  foo.bar.number:
    lowerthan: 200
```

#### check_bool

The value must be a boolean.

The generated boolean must satisfy the provided requirement.

The requirement can be:

* `is`

Example:
```
file: pillar/global/directory.yml
variables:
  pillar: {}
  __grains__: {}
check_bool:
  foo.bar.enabled:
    is: true
```
