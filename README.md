# Article Analyzer

This repo presents the work of the ReaderBench research team to identify articles with a large N (N > 1000).

The code is publically available and it is structured as followed:
- crawl -> code used for crawling articles from different sources
- parsers -> code used for parsing pdfs
- n1000-analysis -> code used for identifying news with N > 1000 (using only heuristics)
- utils -> utility functions used in other packages
- examples -> code used for experimenting different features

For finding the potential large N articles using our method, the following steps must be followed:
- Download the Eric dataset from https://largenineducation.org/datasets-and-publications (the corpus must be located in the main folder where n1000.py script is located).
- The FLAN T5 model must be installed. If it is not automatically installed by the transformers library, it can be manually installed from https://github.com/google-research/t5x.
- Run `python n1000.py 2021`, where 2021 represents the year for which all articles will be verified for potential large N.
