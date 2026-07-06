# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/damien-robotsix/robotsix-calendar-agent/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                          |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|-------------------------------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| src/robotsix\_calendar\_agent/\_\_init\_\_.py                 |        6 |        0 |        0 |        0 |    100% |           |
| src/robotsix\_calendar\_agent/\_\_main\_\_.py                 |        4 |        4 |        2 |        0 |      0% |       3-8 |
| src/robotsix\_calendar\_agent/add\_to\_calendar\_handler.py   |      112 |        0 |       32 |        0 |    100% |           |
| src/robotsix\_calendar\_agent/agent.py                        |      134 |       40 |       36 |        1 |     70% |123-140, 169, 181, 191, 202, 231-244, 260-268, 275, 289, 302, 318, 325, 334, 345, 360, 390-\>392 |
| src/robotsix\_calendar\_agent/caldav\_client/\_\_init\_\_.py  |       96 |       11 |       34 |        1 |     91% |180-181, 191-194, 224-230 |
| src/robotsix\_calendar\_agent/caldav\_client/\_shared.py      |      112 |        2 |        8 |        2 |     97% |  120, 156 |
| src/robotsix\_calendar\_agent/caldav\_client/calendar\_ops.py |       85 |        2 |       20 |        2 |     96% |  194, 233 |
| src/robotsix\_calendar\_agent/caldav\_client/contact\_ops.py  |      101 |       11 |       32 |        4 |     89% |42, 64-66, 72-74, 81-84 |
| src/robotsix\_calendar\_agent/caldav\_client/task\_ops.py     |       18 |        0 |        2 |        0 |    100% |           |
| src/robotsix\_calendar\_agent/entrypoint.py                   |       27 |        0 |        0 |        0 |    100% |           |
| src/robotsix\_calendar\_agent/healthcheck.py                  |       46 |        1 |       12 |        1 |     97% |        89 |
| src/robotsix\_calendar\_agent/intent\_parser.py               |       56 |        0 |        2 |        0 |    100% |           |
| src/robotsix\_calendar\_agent/logging\_config.py              |       32 |        1 |        6 |        1 |     95% |        33 |
| src/robotsix\_calendar\_agent/settings.py                     |       19 |        0 |        2 |        0 |    100% |           |
| **TOTAL**                                                     |  **848** |   **72** |  **188** |   **12** | **91%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/damien-robotsix/robotsix-calendar-agent/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/damien-robotsix/robotsix-calendar-agent/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/damien-robotsix/robotsix-calendar-agent/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/damien-robotsix/robotsix-calendar-agent/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Fdamien-robotsix%2Frobotsix-calendar-agent%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/damien-robotsix/robotsix-calendar-agent/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.