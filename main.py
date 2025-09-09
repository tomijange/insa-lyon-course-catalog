import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
import sys
from bs4 import BeautifulSoup
import requests
import pymupdf

async def main():
  # get args
  if len(sys.argv) > 1 and sys.argv[1] == "fetch":
    courses = await fetch_courses()
    with open("courses.json", "w", encoding="utf-8") as f:
      json.dump(courses, f, ensure_ascii=False, indent=2)
  else:
    with open("courses.json", "r", encoding="utf-8") as f:
      courses = json.load(f)
  
  print(f"Total courses loaded: {len(courses)}")
  
  # make a markdown website by department
  courses_by_department = dict()
  for course in courses:
    dept = course['course']['department']
    if dept == "":
      dept = "Unknown"
    
    dept = dept.replace(" & ", "-").replace(" / ", "-").replace(" ", "-")
    
    if dept not in courses_by_department:
      courses_by_department[dept] = []
    courses_by_department[dept].append(course)
    
  # create output directory
  if not os.path.exists("output/departements"):
    os.makedirs("output/departements")
  
  with open("output/index.md", "w", encoding="utf-8") as f:
    f.write("# INSA Lyon Course Catalog\n\n")
    f.write("## Departments\n\n")
    for departement in courses_by_department.keys():
      f.write(f"- [{departement}](./departements/{departement}.md)\n")
    f.write("\n---\n\n")
    
  for departement, courses in courses_by_department.items():
    with open(f"output/departements/{departement}.md", "w", encoding="utf-8") as f:
      for course in courses:
        f.write(f"## {course['course']['title']} ({course['course']['niveau']})\n\n")
        f.write(f"- Department: {course['course']['department']}\n")
        f.write(f"- Language: {course['course']['langue']}\n")
        f.write(f"- Semester: {course['course']['semestre']}\n")
        f.write(f"- Credits: {course['course']['credits']}\n")
        f.write(f"- Hours: {course['course']['hours']}\n")
        f.write(f"- Internal Name: {course['course']['internal_name']}\n")
        f.write(f"- [Link]({course['course']['link']})\n\n")
        
        f.write("### Course Details\n\n")
        for key, values in course['details'].items():
          f.write(f"#### {key}\n\n")
          for value in values:
            f.write(f"{value}\n")
          f.write("\n")
        
        f.write("\n---\n\n")


async def fetch_courses():
  courses = get_courses()
  print(f"Total courses fetched: {len(courses)}")
  executor = ThreadPoolExecutor(max_workers=2)

  
  async def process_course(course, executor):
    for i in range(3):
      try:
        details = await loop.run_in_executor(executor, get_course_page, course)
        course_object = {
          "course": course,
          "details": details
        }
        print(f"Processed course: {course['title']}")
        return course_object
      except Exception as e:
        if i < 2:
          print(f"Retrying course {course['title']} due to error: {e}")
          await asyncio.sleep(2)
        else:
          print(f"Error processing course {course['title']}: {e}")


  # await all
  course_list = await asyncio.gather(*[process_course(course, executor) for course in courses])
  
  return course_list

def get_course_page(course):
  url = course['link']
  response = requests.get(url)
  if response.status_code != 200:
      raise Exception(f"Failed to fetch course page: {response.status_code}")

  doc = pymupdf.open(stream=response.content, filetype="pdf")
  for page in doc:  # iterate the document pages
    
    # read page text as a dictionary, suppressing extra spaces in CJK fonts
    blocks = page.get_text("dict", flags=11)["blocks"]
    
    all_blocks = []
    for b in blocks:  # iterate through the text blocks
      # print("\nBlock bbox:", b)  # block bounding box
      block_texts = []
      all_blocks.append(block_texts)
      
      for l in b["lines"]:  # iterate through the text lines
        for s in l["spans"]:  # iterate through the text spans
          # font_properties = "Font: '%s' (), size %g, color #%06x" % (
          #     s["font"],  # font name
          #     # flags_decomposer(s["flags"]),  # readable font flags
          #     s["size"],  # font size
          #     s["color"],  # font color
          # )
          
          
          # print("Text: '%s'" % s["text"])  # simple print of text
          # # print(font_properties)
          
          estimated_type = "normal"
          if s["font"].lower().find("bold") != -1 and s["size"] >= 9:
            estimated_type = "title"
          elif s["size"] == 10 and s["color"] == 0x004d70:
            estimated_type = "title"
          
          block_texts.append({
            "text": s["text"],
            "font": s["font"],
            "size": s["size"],
            "color": s["color"],
            "estimated_type": estimated_type
          })

    information_list = dict()
    current_object = None
    
    for block in all_blocks:
      for texts in block:
        if texts["estimated_type"] == "title" or current_object is None:
          current_object = []
          information_list[texts["text"]] = current_object
        elif texts["estimated_type"] == "normal":
          current_object.append(texts["text"])


  return information_list

def get_courses():
    url = "https://www.insa-lyon.fr/en/formation/offre-de-formation"
    response = requests.post(url, data={
      "op": "search",
    })
    if response.status_code != 200:
        print(f"Failed to fetch page: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    
    list = soup.find("div", class_="liste-offre-formations")

    courses_list = []


    for h3 in list.find_all("h3"):
      department = h3.get_text(strip=True)
      courses = h3.find_next_sibling("div", class_="contenu-liste")

      formation = courses.find_all("div", class_="formation")
      
      for f in formation:
        a = f.find("a")
        niveau = f.find("span", class_="niveau").get_text(strip=True)
        title = f.find("span", class_="spe").get_text(strip=True)
        link = a['href']
        
        langue = f.find("span", class_="langue").get_text(strip=True)
        semestre = f.find("span", class_="semestre").get_text(strip=True)
        # yeah so the first "credits" is the credits and the second is the hours
        credits_span = f.find("span", class_="credits")
        credits = credits_span.get_text(strip=True)
        hours = credits_span.find_next("span", class_="credits").get_text(strip=True)
        
        internal_name = f.find("span", class_="profil").get_text(strip=True)
      
        obj = {
          "department": department,
          "niveau": niveau,
          "title": title,
          "link": link,
          "langue": langue,
          "semestre": semestre,
          "credits": credits,
          "hours": hours,
          "internal_name": internal_name
        }
        
        courses_list.append(obj)    
    return courses_list
    

if __name__ == "__main__":
  loop = asyncio.get_event_loop()
  loop.run_until_complete(main())
