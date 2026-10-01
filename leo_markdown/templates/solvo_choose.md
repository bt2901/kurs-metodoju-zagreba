#### {{ unit.title or enhavo.fasado['Elektu la ĝustan opcion'] }}

{% for demando in unit['items'] %}
{% for opcio in demando.options if opcio.correct %}
- {{ demando.question }} **{{ opcio.text }}**
{% endfor %}
{% endfor %}
