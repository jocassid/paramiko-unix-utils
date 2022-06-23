#!/usr/bin/env python3

from abc import ABC, abstractmethod
from getpass import getpass
from itertools import count
from os import environ
from re import compile as re_compile
from sys import stderr as sys_stderr
from typing import Any, List, Tuple

from paramiko.client import SSHClient


def exec_command_stream_output(
        ssh_client: SSHClient,
        command: str,
        max_lines: int = 10_000,
):
    stdin, stdout, stderr = ssh_client.exec_command(
        command
    )

    for i in count(1):
        if 0 < max_lines < i:
            break

        stdout_line = stdout.readline()
        stderr_line = stderr.readline()

        if not any([stdout_line, stderr_line]):
            break

        if stdout_line:
            yield stdout_line.strip(), False

        if stderr_line:
            yield stderr_line.strip(), True


class Command(ABC):

    def __init__(self, executable: str):
        self.executable = executable
        self.args = []

    def build_command(self) -> str:
        pieces = self.args.copy()
        pieces.insert(0, self.executable)
        return ' '.join(pieces)

    @abstractmethod
    def handle_stdout_line(self, line_number: int, line: str) -> None:
        raise NotImplementedError('subclasses should implement')

    @abstractmethod
    def handle_stderr_line(self, line_number: int, line: str) -> None:
        raise NotImplementedError('subclasses should implement')

    def execute(self, ssh_client: SSHClient) -> None:
        stdout_line_num = 0
        stderr_line_num = 0
        output = exec_command_stream_output(
            ssh_client,
            self.build_command(),
        )
        for line, is_stderr in output:
            if is_stderr:
                stderr_line_num += 0
                self.handle_stderr_line(stderr_line_num, line)
                continue
            stdout_line_num += 1
            self.handle_stdout_line(stdout_line_num, line)


class StderrCachingCommand(Command):

    def __init__(self, executable):
        super().__init__(executable)
        self.stderr_lines = []

    def handle_stdout_line(self, line_number: int, line: str) -> None:
        return super().handle_stdout_line(line_number, line)

    def handle_stderr_line(self, line_number: int, line: str) -> None:
        super().handle_stderr_line(line_number, line)
        self.stderr_lines.append(line)


class Df(StderrCachingCommand):
    """df - Shows amount of free disc space"""

    def __init__(self):
        super().__init__('df')
        self.run_user_regex = re_compile(r'/run/user/(\d+)/doc')
        self.treat_stderr_as_stdout = False

    def parse_line(self, line_number: int, line: str) -> Any:
        pass

    def handle_stderr_line(self, line_number: int, line: str) -> None:
        if not self.treat_stderr_as_stdout:
            if self.run_user_regex.search(line):
                self.treat_stderr_as_stdout = True

        if self.treat_stderr_as_stdout:
            return self.handle_stdout_line(line_number, line)

        super().handle_stderr_line(line_number, line)


def main():

    with SSHClient() as ssh_client:
        ssh_client.load_system_host_keys()
        username: str = 'john'
        password: str = environ.get('PASSWORD') or getpass()
        ssh_client.connect('localhost', username=username, password=password)

        df_command = Df()
        if df_command.execute(ssh_client) != 0:
            print("ERRORS OCCURRED", file=sys_stderr)
            for stderr_line in df_command.stderr_lines:
                print(stderr_line, file=sys_stderr)
            return

        print(df_command.data)




if __name__ == '__main__':
    main()
