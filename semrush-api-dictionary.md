Ph = Keyword bringing users to the URL via Google's top 100 organic search results.
Nq = search volume
Cp = CPC
Co = competition
Nr = number of results
Td = Keyword difficulty - A measure of how hard it is to rank for a specific keyword based on its competition.
Lt =  less than
Kd = Keyword difficulty - Similar to "Td" indicating how challenging it is to rank for a keyword.
Rr = Referring domains - The number of unique websites that link to a specific page.
Fk = "Freshness" score - An indicator of how recently content on a page has been updated.

https://developer.semrush.com/api/v3/analytics/basic-docs/

Dont need Co unless we have specified a domain.
Dont need CPC because we arent doing ads.

intent (In) - 3 - transactional The user wants to find an answer to a specific question.
intent (In) - 0 - commercial The user wants to find a specific page, site, or physical location.
intent (In) - 1 - informational The user wants to investigate brands or services.
intent (In) - 2 - navigational The user wants to complete an action (conversion).

related_url2 = f"https://api.semrush.com/?type=phrase_related&key={api_key}&phrase={keyword}&export_columns=Ph,Nq,Kd,In&database=us&display_limit=25&display_sort=kd_desc&display_filter=%2B|Nq|Gt|99|%2B|Nq|Lt|1501|%2B|Kd|Lt|41|%2B|Kd|Gt|9"
