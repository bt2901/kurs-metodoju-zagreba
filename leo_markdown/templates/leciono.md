{% if 'teksto' in printendaj.partoj and 'text' in leciono.md_builtin -%}
  {% include 'teksto.md' %}
{%- endif %}


{% if 'vortoj' in printendaj.partoj and 'vocab' in leciono.md_builtin -%}
  {% include 'vortoj.md' %}
{%- endif %}


{% if 'gramatiko' in printendaj.partoj and 'grammar' in leciono.md_builtin -%}
  {% include 'gramatiko.md' %}
{%- endif %}


{% if 'ekzercoj' in printendaj.partoj and leciono.md_unuoj -%}

### {{ enhavo.fasado['Ekzercoj'] }}


{% for unit in leciono.md_unuoj %}
{% include 'ekzerco_' ~ unit.type|replace('-', '_') ~ '.md' %}

{% endfor %}
{%- endif %}


{% if 'solvoj' in printendaj.partoj and leciono.md_unuoj -%}

### {{ enhavo.fasado['Solvoj'] or 'Solvoj' }}

`\begin{multicols}{2}`{=latex}



{% for unit in leciono.md_unuoj %}
{% include 'solvo_' ~ unit.type|replace('-', '_') ~ '.md' %}


{% endfor %}

`\end{multicols}`{=latex}


{% endif %}
