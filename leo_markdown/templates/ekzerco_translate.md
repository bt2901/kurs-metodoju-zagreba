#### {{ unit.title or enhavo.fasado['Traduku'] }}

{% for vico in unit['items'] %}
  {% for esperante, fontlingve in vico.items() %}
- {{ esperante }}: `\hrulefill`{=latex}

  {% endfor %}
{% endfor %}
