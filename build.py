import json
d = open('/home/claude/anukul/app/app_data.json').read().replace('</', '<\\/')
t = open('/home/claude/anukul/app/template.html').read().replace('__DATA__', d)
open('/home/claude/anukul/app/anukul_control_room.html', 'w').write(t)
print('ok', len(t))
