# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/damien-robotsix/robotsix-calendar-agent/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                                               |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|------------------------------------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| src/robotsix\_calendar\_agent/\_\_init\_\_.py                      |        4 |        0 |        0 |        0 |    100% |           |
| src/robotsix\_calendar\_agent/add\_to\_calendar\_handler.py        |      103 |        0 |       28 |        0 |    100% |           |
| src/robotsix\_calendar\_agent/agent.py                             |      230 |       12 |       68 |        5 |     94% |143, 182-184, 199-207, 390-\>393, 500, 628-\>630 |
| src/robotsix\_calendar\_agent/brokered\_entrypoint.py              |      138 |        3 |       32 |        4 |     96% |90-\>92, 208, 319-\>326, 321-\>320, 373-374 |
| src/robotsix\_calendar\_agent/caldav\_client.py                    |      366 |       26 |       96 |        9 |     92% |124, 160, 281, 303-305, 311-313, 320-323, 464-465, 475-478, 705, 744, 845-851 |
| src/robotsix\_calendar\_agent/component\_agent/\_\_init\_\_.py     |        5 |        0 |        0 |        0 |    100% |           |
| src/robotsix\_calendar\_agent/component\_agent/config\_contract.py |       76 |        2 |       30 |        0 |     98% |   212-213 |
| src/robotsix\_calendar\_agent/component\_agent/settings.py         |       13 |        0 |        2 |        0 |    100% |           |
| src/robotsix\_calendar\_agent/intent\_parser.py                    |       56 |        0 |        2 |        0 |    100% |           |
| src/robotsix\_calendar\_agent/logging\_config.py                   |       24 |        0 |        6 |        0 |    100% |           |
| src/robotsix\_calendar\_agent/settings.py                          |       52 |        0 |        8 |        0 |    100% |           |
| **TOTAL**                                                          | **1067** |   **43** |  **272** |   **18** | **95%** |           |


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