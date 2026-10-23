"""Host checks for refresh separation, date boundaries and relevant live hints."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = r'''
#include "screensaver_ui.h"
#include <cassert>
using namespace screensaver_ui;
int main(){
  assert(tomorrow(2026,12,31)=="2027-01-01");
  assert(tomorrow(2028,2,28)=="2028-02-29");
  assert(tomorrow(2026,2,28)=="2026-03-01");
  assert(fresh(1000,820) && !fresh(1000,819));
  assert(!fresh(1000,0) && !fresh(1000,1100));
  const auto next=tomorrow(2026,10,23);
  assert(pickup_due("2026-10-24",1,next,true));
  assert(!pickup_due("2026-10-23",0,next,true));
  assert(!pickup_due("2026-10-25",1,next,true)); // explicit date wins over stale days
  assert(pickup_due("",1,next,true));
  assert(!pickup_due("",1,next,false)); // yesterday's payload at midnight
  for(const char *state:{"running","starting","ending","rinse","Läuft","Ein","Spülen"})assert(running(state));
  for(const char *state:{"off","idle","finished","clean","paused","delayedstart","unknown","unavailable","Fertig","Aus","Pause"})assert(!running(state));
  for(const char *name:{"Waschmaschine","Trockner","Geschirrspüler"})assert(appliance(name));
  assert(!appliance("Kühlschrank"));
  Plan p;
  p.desired={"1","2","5","9","","2026-10-23","sunny|14.0","Bio\nPapier\n","Waschmaschine\nTrockner\nGeschirrspüler\n"};
  p.prepare(true);p.commit_all();
  p.desired[2]="0";p.desired[3]="0";p.desired[6]="rainy|13.0";
  p.prepare(false);
  assert(!p.has(1) && !p.has(2) && p.has(3) && p.has(4) && p.has(7));
  assert(!p.has(8) && !p.has(9));
  p.commit(3);assert(!p.has(3) && p.has(4) && p.has(7));
  p.commit(4);p.commit(7);assert(!p.pending);
  // Expired payload or ended appliances erases ONLY the two hint rectangles.
  p.desired[7]="";p.desired[8]="";p.prepare(false);
  assert(p.pending==((1<<7)|(1<<8)));
  std::vector<unsigned> parts;
  for(unsigned iteration=0;iteration<9;++iteration){
    if(p.has(iteration+1)){parts.push_back(iteration+1);p.commit(iteration+1);}
  }
  assert((parts==std::vector<unsigned>{8,9}));
  p.prepare(false);assert(!p.pending);
}
'''


class ScreensaverPlanTest(unittest.TestCase):
    def test_regions_and_relevance(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            (work / "plan.cpp").write_text(SOURCE)
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-I",str(ROOT),
                            str(work / "plan.cpp"), "-o", str(work / "plan")], check=True)
            subprocess.run([str(work / "plan")], check=True)


if __name__ == "__main__":
    unittest.main()
