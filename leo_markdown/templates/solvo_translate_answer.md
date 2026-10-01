#### {{ unit.title or enhavo.fasado['Traduku kaj respondu'] }}

{% for vico in unit['items'] %}

##### {{ vico.demando }}

{% for paro in vico.rektatraduko  %}

  {%- if paro is mapping -%}
    {% for esperante, fontlingve in paro.items() %}
- {{ fontlingve }}: {{ esperante }}
    {% endfor %}
  {% endif %}
{% endfor %}

{% endfor %}
