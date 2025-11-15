from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
import numpy as np
import os
import matplotlib.pyplot as plt

#  预览字体文件
def preview_char_paths(paths):
    plt.figure(figsize=(4, 4))
    for path in paths:
        xs = [p[0] for p in path]
        ys = [p[1] for p in path]
        plt.plot(xs, ys, 'k-')  # 绘制黑色轮廓线
    plt.gca().invert_yaxis()  # 字体坐标y轴反向
    plt.axis('equal')
    plt.show()


class pathCollector(BasePen):
    def __init__(self,glyphSet):
        super().__init__(glyphSet)
        self.paths=[]
        self.current=[]
    def _moveTo(self, pt):
        if self.current:
            self.paths.append(self.current)
        self.current=[pt]
    def _lineTo(self,pt):
        self.current.append(pt)

    def _curveToOne(self, p1, p2, p3):
        # 细分贝塞尔曲线为若干线段
        last = self.current[-1]
        import numpy as np
        t = np.linspace(0, 1,3)
        pts = []
        for i in t:
            x = (1-i)**3*last[0] + 3*(1-i)**2*i*p1[0] + 3*(1-i)*i**2*p2[0] + i**3*p3[0]
            y = (1-i)**3*last[1] + 3*(1-i)**2*i*p1[1] + 3*(1-i)*i**2*p2[1] + i**3*p3[1]
            pts.append((x, y))
        self.current.extend(pts)

    def _closePath(self):
        if self.current:
            if self.current[0] != self.current[-1]:
                self.current.append(self.current[0])
            self.paths.append(self.current)
            self.current = []


#  输入字体, 返回字体点数据
def gen_char_paths(char,font_path):
    font=TTFont(font_path)
    cmap=font["cmap"].getBestCmap()
    gid_or_name = cmap.get(ord(char))
    if isinstance(gid_or_name, int):
        glyph_name = font.getGlyphName(gid_or_name)
    else:
        glyph_name = gid_or_name

    glyph_set=font.getGlyphSet()
    glyph=glyph_set[glyph_name]
    pen=pathCollector(glyph_set)
    glyph.draw(pen)
    
    paths=[]
    for i,p in enumerate(pen.paths):
        path=[]
        for c in p:
            position=[round(c[0]*0.2),round(c[1]*0.2)]
            path.append(position)
        paths.append(path)
    return paths

# 分解位移向量并返回内容与步数
def compute_offset(translate):
    ot=translate #oriangle_translate
    content=""
    num=0
    while True:
        if abs(ot[0])==0 and abs(ot[1])==0:
            break
        
        tran_step=[0,0]
        if ot[0]>127:
            ot[0]-=127
            tran_step[0]=127
        elif ot[0]<-127:
            ot[0]+=127
            tran_step[0]=-127
        else:
            tran_step[0]=ot[0]
            ot[0]-=ot[0]
        
        if ot[1]>127:
            ot[1]-=127
            tran_step[1]=127
        elif ot[1]<-127:
            ot[1]+=127
            tran_step[1]=-127
        else:
            tran_step[1]=ot[1]
            ot[1]-=ot[1]
        
        content+=f"8,({tran_step[0]},{tran_step[1]}),"
        num+=3
    # content+="\n"
    return {
        "content":content,
        "step":num
    }

def decompose_vector(vec):
    ot=vec
    content=""
    num=0
    while True:
        if abs(ot[0])==0 and abs(ot[1])==0:
            break
        tran_step=[0,0]
        if ot[0]>127:
            ot[0]-=127
            tran_step[0]=127
        elif ot[0]<-127:
            ot[0]+=127
            tran_step[0]=-127
        else:
            tran_step[0]=ot[0]
            ot[0]-=ot[0]
        
        if ot[1]>127:
            ot[1]-=127
            tran_step[1]=127
        elif ot[1]<-127:
            ot[1]+=127
            tran_step[1]=-127
        else:
            tran_step[1]=ot[1]
            ot[1]-=ot[1]

        content+=f"{tran_step[0]},{tran_step[1]},"
        num+=1

    return {
        "content":content,
        "step":num
    }

# 讲点数据转化为连续的向量数据
def gen_vector_path(path,translate=[0,0]):
    lp=path[0]
    av=[0,0]
    cv=[0,0]
    lv=[0,0]
    n=0
    text=""
    
    t=0
    for p in path[1:]:
        vec=[p[0]-lp[0],p[1]-lp[1]]
        
        # if vec[1]<=-127:
        #     print(vec[1])
        
        av[0]+=p[0]
        av[1]+=p[1]
        
        if p[0]==lp[0] and p[1]==lp[1]:
            lp=p
            continue
        if vec[0]==lv[0] and vec[1]==lv[1]:
            cv[0]+=vec[0]
            cv[1]+=vec[1]
        else:
            if cv != [0, 0]:  # 写入上一个累积向量
                vec_result=decompose_vector(cv)
                text+=vec_result["content"]
                n+=vec_result["step"]
                if t>=7:
                    text+="\n"
                    t=0
                t+=1
            cv = vec.copy()
            lv = vec.copy()
        lp=p
    
    if cv!=[0,0]:
        vec_result=decompose_vector(cv)
        text+=vec_result["content"]
        n+=vec_result["step"]
        
        # text+=f"{cv[0]},{cv[1]},\n"
        # n+=1
    
    offset=compute_offset(translate)
    
    text=f"\n2,\n{offset["content"]}\n1,\n9,\n{text}0,0,"
    n=n*2+5+offset["step"]
    
    return {
        "all_vec":av,
        "text":text,
        "step":n
    }

def main(text,font_path,out_path):
    char_offset=[0,0]
    move_offset=[0,0]
    
    all_step=0
    all_content=""
    
    for i,char in enumerate(text):
        char_paths=gen_char_paths(char,font_path)
        # preview_char_paths(char_paths)
        file_content=""
        num=0
        
        last_y=char_paths[-1][0][1]
        last_end=[0,0]
        
        begin_y=char_paths[0][0][1]
        
        for n,path in enumerate(char_paths):
            start_point=[path[0][0],path[0][1]]
            
            offset=[start_point[0]-last_end[0],start_point[1]-last_end[1]]
            last_end=start_point
            
            result=gen_vector_path(path,offset)
            note=result["text"]
            note_num=result["step"]
            file_content+=f"{note}"
            
            if n==0:
                num+=note_num
            else:
                num+=note_num
        
        all_content+=file_content
        
        # 计算字体之间的偏移
        char_offset=[-char_paths[-1][0][0],-char_paths[-1][0][1]]
        char_offset_result=compute_offset(char_offset)
        move_offset[0]+=180
        move_offset_result=compute_offset(move_offset)
        
        all_content+="2,"
        all_content+=char_offset_result["content"]
        all_content+=move_offset_result["content"]
        
        all_step+=num+1
        all_step+=char_offset_result["step"]
        all_step+=move_offset_result["step"]

    all_step+=1
    file_content=f"*1,{all_step},N\n{all_content}0\n"
    print(all_step)
    if all_step>2000:
        print("步数大于2000,超限,请更换字体")

    with open(out_path,mode="w",encoding="utf-8")as f:
        f.write(file_content)
    # print(char_paths)

if __name__=="__main__":
    text="测试"
    font_path=r"test.ttf"
    out_path=r"test.shp"

    main(text,font_path,out_path)