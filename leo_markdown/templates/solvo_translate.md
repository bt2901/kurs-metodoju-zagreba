#### {{ unit.title or enhavo.fasado['Traduku'] }}

{% for vico in unit['items'] %}
  {% for esperante, fontlingve in vico.items() %}
- {{ esperante }}: {{fontlingve if fontlingve is string else fontlingve|join(', ')}}
  {% endfor %}
{% endfor %}
