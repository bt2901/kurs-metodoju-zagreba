#### {{ unit.title or enhavo.fasado['Elektu la ĝustan opcion'] }}

{% for demando in unit['items'] %}
- {{ demando.question }}
{% for opcio in demando.options %}
  - {{ opcio.text }}
{% endfor %}

{% endfor %}
