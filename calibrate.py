from psychopy.visual.windowwarp import Warper
from psychopy import visual, core, event

# mywin = visual.Window([608,684],monitor='DLP',screen=1,
                     # useFBO = True, color='white')

mywin = visual.Window([608,684],monitor='DLP',screen=1,
                     useFBO = True, color='black', units='norm')


warper = Warper(mywin,
                    # warp='spherical',
                    warp='warpfile',
                    warpfile = 'calibratedBallImage.data',
                    warpGridsize = 300,
                    eyepoint = [0.5, 0.5],
                    flipHorizontal = False,
                    flipVertical = False)

rect1 = visual.Rect(win=mywin, size=(0.1,0.1), pos=[0,0], lineColor=None, fillColor='white',units='norm')
rect2 = visual.Rect(win=mywin, size=(0.1,0.1), pos=[0,-0.5], lineColor=None, fillColor='white',units='norm')
rect3 = visual.Rect(win=mywin, size=(0.1,0.1), pos=[0,0.5], lineColor=None, fillColor='white',units='norm')
rect4 = visual.Rect(win=mywin, size=(0.1,0.1), pos=[0.5,0], lineColor=None, fillColor='white',units='norm')
# circ1 = visual.Circle(win=mywin, size=(0.1,0.1), pos=[0.5, 0.5], lineColor=None, fillColor='white',units='norm')



rect1.draw()
rect2.draw()
rect3.draw()
rect4.draw()
# circ1.draw()

mywin.flip()
event.waitKeys()
mywin.close()