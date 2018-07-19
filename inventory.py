from subprocess import PIPE, Popen


def hosts(inventory_file='hosts'):

  stdout, status = Popen('''
  for each in `cat {0] | grep -v '^\(\[.*\]$\|#\)' | xargs`; do
      if [[ $each = *"["* ]] && [[ $each = *"]"* ]]; then
          for each in $(eval echo $(sed 's/\[/{/g' <<<${each} | sed 's/]/}/g' | sed 's/:/../g' )); do
              echo $each
          done
      else
          echo $each
      fi
  done
  '''.format(inventory_file), shell=True, stdout=PIPE, stderr=PIPE).communicate()
