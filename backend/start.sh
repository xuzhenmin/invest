#!/bin/bash

# 设置 pyenv 环境
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# 使用正确的 Python 版本
pyenv shell 3.10.6

# 运行应用
python /var/www/invest/backend/app.py > ../backend_log.out 3>&1 & 
