from psychopy.visual.windowwarp import Warper
from psychopy import visual, core, event
import numpy as np

from psychopy.visual.windowframepack import ProjectorFramePacker

# mywin = visual.Window([608,684],monitor='DLP',screen=0,
                     # useFBO = True, color='black', units='norm')

mywin = visual.Window([608,684],monitor='DLP',screen=1,
                     useFBO = True, color='black', units='norm')

# framepacker = ProjectorFramePacker(mywin)

# mywin = visual.Window([684,608],monitor='DLP',screen=0,
#                      useFBO = True, color='black', units='norm')

# warper = Warper(mywin,
#                     warp='spherical',
#                     # warp='warpfile',
#                     # warpfile = 'calibratedBallImage.data',
#                     warpGridsize = 300,
#                     eyepoint = [0.5, 0.5],
#                     flipHorizontal = False,
#                     flipVertical = False)

warper = Warper(mywin,
                    # warp='spherical',
                    warp='warpfile',
                    warpfile = 'calibratedBallImage.data',
                    warpGridsize = 300,
                    eyepoint = [0.5, 0.5],
                    flipHorizontal = False,
                    flipVertical = False)

# rect1 = visual.Rect(win=mywin, size=(0.1,0.1), pos=[0,0], lineColor=None, fillColor='white',units='norm')

# rect2 = visual.Rect(win=mywin, size=(0.1,0.1), pos=[0,-0.6], lineColor=None, fillColor='white',units='norm')
# rect3 = visual.Rect(win=mywin, size=(0.1,0.1), pos=[0,0.5], lineColor=None, fillColor='white',units='norm')
# rect4 = visual.Rect(win=mywin, size=(0.1,0.1), pos=[0.6,0], lineColor=None, fillColor='white',units='norm')

# circ1 = visual.Circle(win=mywin, radius=0.1, pos=[0.1, -0.5], lineColor=None, fillColor='white',units='norm')
# circ1.draw()
# mywin.flip()

# # rect2 = visual.Rect(win=mywin, size=(0.1,0.1), pos=[0.1,-0.5], lineColor=None, fillColor='white',units='norm')
# # rect2.draw()
# # mywin.flip()

# for t in np.arange(1000):

# 	print(t)
# 	circ1.radius = t/5000
# 	# circ1.radius = t/1000
# 	# rect2.size = (t/5000,t/5000)
# 	# rect2.draw()
# 	circ1.draw()	
# 	mywin.flip()




# rect1.draw()
# rect2.draw()
# rect3.draw()
# rect4.draw()


# mywin.flip()
# event.waitKeys()
# mywin.close()

## creating grid
num_check = 30
check_size = [0.08, 0.08]

location = [0, 0]
# generate loc array 
loc = np.array(location) + np.array(check_size) // 2

# array of rgbs for each element (2D)
colors = np.stack((np.random.random(num_check ** 2),)*3, -1)

# array of coordinates for each element
xys = []
# populate xys
low, high = num_check // -2, num_check // 2

for y in range(low, high):
    for x in range(low, high):
        xys.append((check_size[0] * x,
                    check_size[1] * y))


stim = visual.ElementArrayStim(mywin,
                               xys=xys,
                               fieldPos=loc,
                               colors=colors,
                               nElements=num_check**2,
                               elementMask=None,
                               elementTex=None,
                               sizes=(check_size[0],
                                      check_size[1]))

stim.size = (check_size[0] * num_check,
             check_size[1] * num_check)

for i in range(60):
    stim.draw()
    mywin.flip()

# mywin.flip()
event.waitKeys()
mywin.close()