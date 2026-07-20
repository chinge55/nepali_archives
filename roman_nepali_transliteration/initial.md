
## Goal: 
On top of only providing the archives, this project aims to provide a new feature. Conversion from romanized nepali (written in english) to actual nepali unicode. 
Eg: 'mero nam ho'-> 'मेरो नाम हो '
It also can be written as: 'mero naam ho', and they mean the same thing. 

## Initial Dataset
1. https://huggingface.co/datasets/Saugatkafley/Nepali-Roman-Transliteration
2. https://huggingface.co/datasets/nirajandhakal/Devnagari-Romanized-Pair

## Stage 1:
1. Curated Rule lookup
2. Exact lexicon lookup
3. Normalized form lookup 
4. Tiny neural Fallback
5. Return Top 5 Candidates

## Design Constraints:
The feature should be extremely easy to use. Any model that we create should be small in size, should not affect performance even if the model is not loaded as well. So, it is downloading in the background, and people can still use it. For now, we will have next-word conversion, with short-context re-ranking. This stage will not have a complete sentence translation. 

Because we will be giving it for free, the site should remain static, meaning the model should be small, the algorithm should be fast. The primary thing to optimize is performance, not accuracy. Accuracy can never be correct and the UI/UX should complement the user. 

It should work good for PC but smartphones are extremely important as well.


1. Task 1 will always be literature review. We build it like a research objective for the product, and then only go to development.
2. First thing to do is to make rules for the project, absolutely sure on the things we will do and the things we will not do. 
3. The nepali archive itself is made because nepali language texts and tools are not accessible to normal people. This project should complement that. A good project is useless if it is difficult to use. Of course, it should be technologically advanced but the utmost priority is usability. Even small details like, how the user will copy, how the user will fix mistakes etc, should be meticulously crafted. Treat the users are tech-illiterate.

