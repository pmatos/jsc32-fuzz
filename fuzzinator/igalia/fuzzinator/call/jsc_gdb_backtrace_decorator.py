# Copyright (c) 2016-2020 Renata Hodovan, Akos Kiss.
# Copyright (c) 2021 Paulo Matos, Igalia S.L.
#
# Licensed under the BSD 3-Clause License
# <LICENSE.rst or https://opensource.org/licenses/BSD-3-Clause>.
# This file may not be copied, modified, or distributed except
# according to those terms.
#
# FIXME: is there an easier way to do this, by maybe just extending the
# decorator?

import logging
import os
import pexpect

from fuzzinator.config import as_dict, as_pargs, as_path, decode
from fuzzinator.call import CallableDecorator

logger = logging.getLogger(__name__)


class JSCGdbBacktraceDecorator(CallableDecorator):
    """
    Decorator for subprocess-based SUT calls with file input to extend issues
    with ``'backtrace'`` property.

    **Mandatory parameter of the decorator:**

      - ``command``: string to pass to GDB as a command to run (all occurrences
        of ``{test}`` in the string are replaced by the actual name of the test
        file). Also (all occurrences of ``{options}}`` in the string are replaced 
        by the actual list of options).

    **Optional parameters of the decorator:**

      - ``cwd``: if not ``None``, change working directory before GDB/command
        invocation.
      - ``env``: if not ``None``, a dictionary of variable names-values to
        update the environment with.

    The new ``'backtrace'`` issue property will contain the result of GDB's
    ``bt`` command after the halt of the SUT.

    **Example configuration snippet:**

        .. code-block:: ini

            [sut.foo]
            call=fuzzinator.call.SubprocessCall
            call.decorate(0)=JSCGdbBacktraceDecorator

            [sut.foo.call]
            # assuming that {test} is something that can be interpreted by foo as
            # command line argument
            command=./bin/foo {options} {test}
            cwd=/home/alice/foo
            env={"BAR": "1"}

            [sut.foo.call.decorate(0)]
            command=${sut.foo.call:command}
            cwd=${sut.foo.call:cwd}
            env={"BAR": "1", "BAZ": "1"}
    """

    def decorator(self, command, cwd=None, env=None, encoding=None, **kwargs):
        def wrapper(fn):
            def filter(*args, **kwargs):
                issue = fn(*args, **kwargs)
                if not issue:
                    return issue

                try:
                    child = pexpect.spawn('gdb', ['-ex', 'set width unlimited', '-ex', 'set pagination off', '--args'] + as_pargs(command.format(test=kwargs['test'], options=issue['options'])),
                                          cwd=as_path(cwd) if cwd else os.getcwd(),
                                          env=dict(os.environ, **as_dict(env or '{}')))
                    child.expect_exact('(gdb) ')
                    child.sendline('run')
                    child.expect_exact('(gdb) ')
                    child.sendline('bt')
                    child.expect_exact('(gdb) ')
                    backtrace = child.before
                    child.terminate(force=True)
                    issue['backtrace'] = decode(backtrace, encoding)
                except Exception as e:
                    logger.warning('Failed to obtain gdb backtrace', exc_info=e)

                return issue

            return filter
        return wrapper
