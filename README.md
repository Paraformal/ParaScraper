# Scraper Project Documentation

## Overview

Peter El Khoury  
Mobile Numbers: +961 81 280 551 / +961 76 19 49 19  
Email: peter.elkhoury@std.balamand.edu.lb

:warning: **Attention:** PLEASE READ TO THE END !!!

So first of all, the scraper I made is using "Scrapy" python lib, scrapy allows requests 
to desired url without having to deal with api limits, captchas, anti-scraping security and more.

### 1. Laws Scraper

While studying the website and thinking about the best way to scrape data from it, i noticed
that the url are mostly the same and just minor parts in them (query params) changes (lawId, Year),
thus i decided to make 3 calls to 3 api like this:

1. First api call will get me the years that are offered on the website, those years will be saved
   in a json file.
2. After that we loop while calling the second api, since it take year as query params, we will loop
   until years saved in the previous json are done. This api call will result in all the laws Id's.
3. While looping, calling the second api we loop to call the third api, this one take the law Id as
   query params. 

   N.B.: At this point i faced 2 problems, one api allow to get the law detail by law id but it requires 
           another api call to get the law articles ( al mawad ). Making the whole proccesse very very slow
           EVEN with multithreading techniques used. 

         Thus i chose the option to call the api that the website offer to visualize the full data without
           having to call any other api. This made the proccesse faster and more reliable, but i was obliged
           to scrape the html as it is not the values only. This made the data bigger thus instead of sorting 
           it while saving into html files, i saved them randomly and a index.html file will be creating with
           redirects to each law and each material. This roundabout cut the scraping time in half (from 2h to 65min),
           and it freed me from parsing desired data one by one.

         Another problem, my hardware resources weren't enough to handle saving all those data to the database, 
         Don't get me wrong, but i did it in the most efficient way I know and still my laptop could not handle all
         the data saving. That's why i had to submit the sql schema for the law database empty of data.

I used multithreading to make the scraping process much faster or it would take hours to finish.


### 2. Rulings Scraper

Same idea as the laws scraping, i noticed we can access the data from changing minor settings
in the url query params, so i did the same.

Url call 1 gives you years available,
Url call 2 (loop) with the years parsed from the first call.
Url call 3 take the pages to parse for a specified year from the data of call 2
and the last Url call will take the year, page, ruling id from previous parsed data,
this last url call will get the detail of each ruling.


In this case I parsed each data manually and formed a tabular html format to display the data,
The data comes out sorted by Year and there is optional search in each html file generated.

N.B.: Each html file has a limit of 10mb in size, but in order to divide a year across 2 files,
       I allowed in certain cases to extend the size cap untill the year data is done, after that
       a new html file is generated to continue filling the data.

As for the sql database, data is saved in a ramdom order, since we can write a simple query to get the 
   data sorted, there is no necessity to loose time and hardware resource on saving data sorted in the db.

### 3. Running the Scraper

a- pip install requirements.txt

b- For the rulings: 

   -> python rulings_spider.py (here data is simpler thats why the data will be extracted and saved instantly
                                   in the database)

  For the laws:

   -> python laws_spider.py   (this will scrape and extract data to html)
   -> python processLaws.py   (this will save data to database [its a seperate command due
                                   to the huge data ammount that will make the scraping process 
                                   innificient, slow and risk errors])


### 4. DbHandler.py

-> For better code reusability and scaling, i seperated the db operations as function in this file.
-> These function will be called in each scraper to save data in db.
-> This way errors will be easier to detect and fix, code will be clean.

### 5. Other (.py) files are required for scrapy lib. (TO NOT MESS WITH)


Finnaly i would've liked to develop a main.py that will combine both scrapper in one runnable program,
that will allow the user to custumize multithreading workes, use proxies etc... 
But unfurtunately time wasn't in my favor to develop it to the fullest and make it presentation ready.

More improvements can be made speed wise, and data organizing wise, it's a wide text improvements more than
I can count can be implemented.

Thus I hope my work will be satisfying and enough to get you attention even if a little.

Thank You!
