import json 
import urllib2
import base64
import os
import datetime
import sys
#config
#base64string = base64.encodestring('username:password')
base64string = "thebase64ofusername:password\n"
apikey= 'API key from trakt.tv'
username ='your username'
apipath='/user/calendar/shows.json/'
tmppath= '/tmp/trakt/'  #path to where json data is stored
#funcs


def user_cal_shows():
    request = urllib2.Request("https://api.trakt.tv/user/calendar/shows.json/" + apikey + "/" + username)
    request.add_header("Authorization", "Basic %s" % base64string)
    return json.load(urllib2.urlopen(request))

def outputrun():
    for i in range(len(out)):
        for b in range(len(out[i]['episodes'])):
            in_watch = out[i]['episodes'][b]['show']['in_watchlist'] #True
            #make sure the show is in the watch list
            if in_watch == True:
                showname = out[i]['episodes'][b]['show']['title']  #Fringe
                ep_name = out[i]['episodes'][b]['episode']['title']  #In Absentia
                network = out[i]['episodes'][b]['show']['network']  #FOX
                airtime = out[i]['episodes'][b]['show']['air_time']  #9:00pm
                season = out[i]['episodes'][b]['episode']['season']  #5
                ep_num = out[i]['episodes'][b]['episode']['number']  #2
                airday = out[i]['episodes'][b]['show']['air_day']  #Friday
                runtime = out[i]['episodes'][b]['show']['runtime']  #60v    
                print showname + " airs at \033[1m" +  airtime + "\033[0m on \033[1m" + airday + "\033[0m"
                print "\t " + str(season) + "." + str(ep_num) + " - " + ep_name + " \033[1m" + network +"\033[0m"
                print "\t watchlist: " + str(in_watch) + " - runtime: " + str(runtime) + "min"

def update_json():
    out = user_cal_shows()
    #overwrites any data there
    with open(tmppath+"data","wb") as fp:
        json.dump(out,fp)
    return out


#caching, sees if cache folder is there, if not make it
#if it is, it gets the date from the cache
if not os.path.exists(tmppath+"data"):
    if not os.path.exists(tmppath):
        os.makedirs(tmppath)
    out = update_json()
else:
    #load from the file
    with open(tmppath+"data", "rb") as fp:
        out = json.load(fp)
   #compare the date
    if str(out[0]['date']) != str(datetime.date.today()):
       #not the same, update list 
       out = update_json()
    if len(sys.argv) > 1:
        if str(sys.argv[1]) == "reset":
           out = update_json() 
outputrun()
